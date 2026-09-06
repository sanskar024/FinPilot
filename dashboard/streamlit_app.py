"""
FinPilot dashboard — Streamlit app. Talks ONLY to the Node API, never
directly to Postgres or the Python agent service (see README architecture).

Run with: streamlit run streamlit_app.py
Requires NODE_API_URL env var (defaults to http://localhost:4000).
"""

import os

import pandas as pd
import requests
import streamlit as st

NODE_API_URL = os.getenv("NODE_API_URL", "http://localhost:4000")
DEFAULT_ORG_ID = 1

st.set_page_config(page_title="FinPilot", page_icon="💰", layout="wide")
st.title("💰 FinPilot — AI Financial Copilot")


def get(path, params=None):
    try:
        resp = requests.get(f"{NODE_API_URL}{path}", params=params, timeout=10)
        resp.raise_for_status()
        return resp.json(), None
    except requests.exceptions.RequestException as e:
        return None, str(e)


def post(path, json=None):
    try:
        resp = requests.post(f"{NODE_API_URL}{path}", json=json, timeout=15)
        resp.raise_for_status()
        return resp.json(), None
    except requests.exceptions.RequestException as e:
        return None, str(e)


org_id = st.sidebar.number_input("Organization ID", min_value=1, value=DEFAULT_ORG_ID, step=1)

tab_dashboard, tab_chat = st.tabs(["📊 Dashboard", "💬 Ask the CFO"])

# ---------------------------------------------------------------------------
# Dashboard tab
# ---------------------------------------------------------------------------
with tab_dashboard:
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Cash Flow (current period)")
        cashflow, err = get("/api/cfo/cashflow", {"org_id": org_id})
        if err:
            st.error(f"Could not load cashflow: {err}")
        elif cashflow:
            m1, m2, m3 = st.columns(3)
            m1.metric("Inflows", f"{cashflow['inflows']:,.0f}")
            m2.metric("Outflows", f"{cashflow['outflows']:,.0f}")
            m3.metric("Net Cashflow", f"{cashflow['net_cashflow']:,.0f}")

            if cashflow["outflow_by_category"]:
                cat_df = pd.DataFrame(
                    list(cashflow["outflow_by_category"].items()), columns=["Category", "Amount"]
                ).sort_values("Amount", ascending=False)
                st.bar_chart(cat_df.set_index("Category"))

            st.caption(cashflow["explanation"])

    with col2:
        st.subheader("Runway")
        runway, err = get("/api/cfo/runway", {"org_id": org_id})
        if err:
            st.error(f"Could not load runway: {err}")
        elif runway:
            status_emoji = {"critical": "🔴", "warning": "🟡", "healthy": "🟢", "cashflow_positive": "🟢"}
            st.metric(
                "Months of Runway",
                runway["runway_months"] if runway["runway_months"] is not None else "∞",
                delta=status_emoji.get(runway["runway_status"], ""),
            )
            st.caption(runway["explanation"])

    st.divider()

    st.subheader("Forecast — next few weeks")
    forecast, err = get("/api/cfo/forecast", {"org_id": org_id})
    if err:
        st.error(f"Could not load forecast: {err}")
    elif forecast:
        forecast_df = pd.DataFrame(forecast["forecast"])
        if not forecast_df.empty:
            forecast_df["week_start"] = pd.to_datetime(forecast_df["week_start"])
            st.line_chart(forecast_df.set_index("week_start")["predicted_net_cashflow"])
        st.caption(forecast["explanation"])

        # Backtest chart — predicted vs actual, so the forecast's accuracy
        # is visible, not just asserted (README point #2).
        backtest = forecast.get("backtest", {})
        if backtest.get("comparison"):
            st.markdown("**Forecast backtest — predicted vs. actual (held-out weeks)**")
            bt_df = pd.DataFrame(backtest["comparison"])
            bt_df["week_start"] = pd.to_datetime(bt_df["week_start"])
            st.line_chart(bt_df.set_index("week_start")[["actual_net_cashflow", "predicted_net_cashflow"]])
            st.caption(f"Mean absolute error: {backtest['mean_absolute_error']:,.2f}")

    st.divider()

    st.subheader("Risk / Anomalies")
    risk, err = get("/api/cfo/risk", {"org_id": org_id})
    if err:
        st.error(f"Could not load risk data: {err}")
    elif risk:
        st.caption(risk["explanation"])
        if risk["outflow_spikes"]:
            st.markdown("**Unusual outflows**")
            st.dataframe(pd.DataFrame(risk["outflow_spikes"])[["date", "category", "amount", "reason"]])
        if risk["inflow_gaps"]:
            st.markdown("**Inflow gaps**")
            st.dataframe(pd.DataFrame(risk["inflow_gaps"])[["month", "actual_inflow", "trailing_average_inflow", "reason"]])

# ---------------------------------------------------------------------------
# Chat tab
# ---------------------------------------------------------------------------
with tab_chat:
    st.subheader("Ask the CFO Agent")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            if msg["role"] == "assistant" and msg.get("agents_used"):
                st.caption(f"Agents used: {', '.join(msg['agents_used'])} — {msg.get('reasoning', '')}")

    question = st.chat_input("Ask about cash flow, runway, forecasts, or risk...")
    if question:
        st.session_state.chat_history.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.write(question)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                result, err = post("/api/cfo/ask", {"org_id": org_id, "question": question})
            if err:
                st.error(f"Could not reach the CFO agent: {err}")
            else:
                st.write(result["answer"])
                st.caption(f"Agents used: {', '.join(result['agents_used']) or 'none'} — {result['reasoning']}")
                st.session_state.chat_history.append(
                    {
                        "role": "assistant",
                        "content": result["answer"],
                        "agents_used": result["agents_used"],
                        "reasoning": result["reasoning"],
                    }
                )
