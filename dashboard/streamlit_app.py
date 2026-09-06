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
        resp = requests.get(f"{NODE_API_URL}{path}", params=params, timeout=60)
        resp.raise_for_status()
        return resp.json(), None
    except requests.exceptions.RequestException as e:
        return None, str(e)


def post(path, json=None):
    try:
        resp = requests.post(f"{NODE_API_URL}{path}", json=json, timeout=90)
        resp.raise_for_status()
        return resp.json(), None
    except requests.exceptions.RequestException as e:
        return None, str(e)


org_id = st.sidebar.number_input("Organization ID", min_value=1, value=DEFAULT_ORG_ID, step=1)

VALID_TYPES = {"inflow", "outflow"}
REQUIRED_COLUMNS = {"date", "amount", "type", "category"}


def validate_import_df(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """
    Pure function: validates an uploaded transactions dataframe against the
    same rules the Node API enforces (kept in sync deliberately — this is a
    client-side pre-check, not a replacement for server-side validation,
    which still runs on every row when it's actually posted).

    Returns (valid_rows_df, list_of_error_messages_for_invalid_rows).
    """
    errors = []
    missing_cols = REQUIRED_COLUMNS - set(df.columns)
    if missing_cols:
        errors.append(f"Missing required column(s): {', '.join(sorted(missing_cols))}")
        return df.iloc[0:0], errors

    valid_mask = pd.Series(True, index=df.index)

    dates_parsed = pd.to_datetime(df["date"], errors="coerce")
    bad_dates = dates_parsed.isna()
    for idx in df.index[bad_dates]:
        errors.append(f"Row {idx + 2}: invalid date '{df.loc[idx, 'date']}'")
    valid_mask &= ~bad_dates

    amounts_numeric = pd.to_numeric(df["amount"], errors="coerce")
    bad_amounts = amounts_numeric.isna() | (amounts_numeric <= 0)
    for idx in df.index[bad_amounts]:
        errors.append(f"Row {idx + 2}: amount must be a positive number, got '{df.loc[idx, 'amount']}'")
    valid_mask &= ~bad_amounts

    bad_types = ~df["type"].isin(VALID_TYPES)
    for idx in df.index[bad_types]:
        errors.append(f"Row {idx + 2}: type must be 'inflow' or 'outflow', got '{df.loc[idx, 'type']}'")
    valid_mask &= ~bad_types

    bad_category = df["category"].isna() | (df["category"].astype(str).str.strip() == "")
    for idx in df.index[bad_category]:
        errors.append(f"Row {idx + 2}: category is required")
    valid_mask &= ~bad_category

    return df[valid_mask], errors


tab_dashboard, tab_chat, tab_import = st.tabs(["📊 Dashboard", "💬 Ask the CFO", "📥 Import Data"])

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

# ---------------------------------------------------------------------------
# Import Data tab
# ---------------------------------------------------------------------------
with tab_import:
    st.subheader("Import your own transaction data")
    st.caption(
        "Upload a CSV to load a real company's transactions instead of the demo data. "
        "Required columns: date, amount, type (inflow/outflow), category. "
        "Description is optional."
    )

    st.markdown("**Step 1 — Choose or create an organization**")
    org_choice = st.radio(
        "Import into",
        ["Use the Organization ID from the sidebar", "Create a new organization"],
        horizontal=True,
    )

    target_org_id = org_id
    if org_choice == "Create a new organization":
        new_org_name = st.text_input("New organization name")
        if st.button("Create organization"):
            if not new_org_name.strip():
                st.error("Organization name can't be empty.")
            else:
                result, err = post("/api/organizations", {"name": new_org_name.strip()})
                if err:
                    st.error(f"Could not create organization: {err}")
                else:
                    st.success(f"Created organization '{result['name']}' with ID {result['id']}. "
                               f"Set the sidebar's Organization ID to {result['id']} to use it.")

    st.divider()
    st.markdown("**Step 2 — Upload your CSV**")

    with st.expander("Show expected CSV format"):
        st.code(
            "date,amount,type,category,description\n"
            "2026-01-05,50000,inflow,revenue,Client payment\n"
            "2026-01-10,15000,outflow,rent,Office rent",
            language="csv",
        )

    uploaded_file = st.file_uploader("Choose a CSV file", type=["csv"])

    if uploaded_file is not None:
        try:
            raw_df = pd.read_csv(uploaded_file)
        except Exception as e:
            st.error(f"Could not read this file as CSV: {e}")
            raw_df = None

        if raw_df is not None:
            valid_df, errors = validate_import_df(raw_df)

            st.write(f"**{len(valid_df)} of {len(raw_df)} rows are valid.**")

            if errors:
                with st.expander(f"⚠️ {len(errors)} row(s) will be skipped — click to see why"):
                    for e in errors:
                        st.text(e)

            if not valid_df.empty:
                st.dataframe(valid_df.head(20))
                if len(valid_df) > 20:
                    st.caption(f"...and {len(valid_df) - 20} more rows")

                st.markdown("**Step 3 — Import**")
                st.warning(
                    f"This will add {len(valid_df)} transaction(s) to Organization ID {target_org_id}. "
                    "This does not overwrite existing data — it adds to it."
                )

                if st.button(f"Import {len(valid_df)} transactions to Org {target_org_id}", type="primary"):
                    progress = st.progress(0, text="Starting import...")
                    succeeded = 0
                    failed = []

                    for i, (_, row) in enumerate(valid_df.iterrows()):
                        payload = {
                            "org_id": int(target_org_id),
                            "date": str(pd.to_datetime(row["date"]).date()),
                            "amount": float(row["amount"]),
                            "type": row["type"],
                            "category": str(row["category"]),
                        }
                        if "description" in row and pd.notna(row.get("description")):
                            payload["description"] = str(row["description"])

                        _, err = post("/api/transactions", payload)
                        if err:
                            failed.append((i + 2, err))
                        else:
                            succeeded += 1

                        progress.progress(
                            (i + 1) / len(valid_df),
                            text=f"Imported {i + 1} of {len(valid_df)}...",
                        )

                    progress.empty()
                    st.success(f"Imported {succeeded} of {len(valid_df)} transactions successfully.")
                    if failed:
                        with st.expander(f"⚠️ {len(failed)} row(s) failed during import"):
                            for row_num, err in failed:
                                st.text(f"Row {row_num}: {err}")