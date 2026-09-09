"""
FinPilot dashboard — Streamlit app. Talks ONLY to the Node API, never
directly to Postgres or the Python agent service (see README architecture).

Run with: streamlit run streamlit_app.py
Requires NODE_API_URL env var (defaults to http://localhost:4000).

Authentication: the dashboard does NOT let the user pick an organization
ID — that would defeat the entire point of the backend's authorization
model. Instead, the user logs in, Node returns a JWT containing their
organization_id, and every subsequent request carries that JWT. The
organization shown is always whichever one the JWT says, never a value
typed into a text box.
"""

import os

import pandas as pd
import requests
import streamlit as st

NODE_API_URL = os.getenv("NODE_API_URL", "http://localhost:4000")

st.set_page_config(page_title="FinPilot", page_icon="💰", layout="wide")


def auth_headers():
    token = st.session_state.get("token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def get(path, params=None):
    try:
        resp = requests.get(f"{NODE_API_URL}{path}", params=params, headers=auth_headers(), timeout=60)
        if resp.status_code == 401:
            _force_logout("Your session has expired — please log in again.")
            return None, "Session expired"
        resp.raise_for_status()
        return resp.json(), None
    except requests.exceptions.RequestException as e:
        return None, str(e)


def post(path, json=None):
    try:
        resp = requests.post(f"{NODE_API_URL}{path}", json=json, headers=auth_headers(), timeout=90)
        if resp.status_code == 401:
            _force_logout("Your session has expired — please log in again.")
            return None, "Session expired"
        resp.raise_for_status()
        return resp.json(), None
    except requests.exceptions.RequestException as e:
        return None, str(e)


def _force_logout(message):
    st.session_state.pop("token", None)
    st.session_state.pop("user", None)
    st.session_state["logout_message"] = message


# ---------------------------------------------------------------------------
# Login gate — nothing below this renders until a valid JWT is in session
# ---------------------------------------------------------------------------
if "token" not in st.session_state:
    st.title("💰 FinPilot — AI Financial Copilot")

    if st.session_state.get("logout_message"):
        st.warning(st.session_state.pop("logout_message"))

    st.subheader("Log in")

    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in")

    if submitted:
        try:
            resp = requests.post(
                f"{NODE_API_URL}/api/auth/login",
                json={"email": email, "password": password},
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                st.session_state["token"] = data["token"]
                st.session_state["user"] = data["user"]
                st.rerun()
            else:
                st.error("Invalid email or password.")
        except requests.exceptions.RequestException as e:
            st.error(f"Could not reach the login service: {e}")

    st.caption(
        "Don't have an account? Ask your organization's admin to register you, "
        "or see SETUP.md for how to bootstrap the first organization."
    )
    st.stop()  # nothing past this point runs until logged in


# ---------------------------------------------------------------------------
# Logged in — everything below runs with a valid JWT in session
# ---------------------------------------------------------------------------
user = st.session_state["user"]

st.sidebar.success(f"Logged in as {user['email']}")
st.sidebar.caption(f"Organization ID: {user['organizationId']} · Role: {user['role']}")
if st.sidebar.button("Log out"):
    st.session_state.pop("token", None)
    st.session_state.pop("user", None)
    st.rerun()

st.title("💰 FinPilot — AI Financial Copilot")

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
# Dashboard tab — every call below sends NO org_id at all. The Node API
# derives it entirely from the JWT in auth_headers(). There is nothing
# for this UI to get wrong here even if it tried.
# ---------------------------------------------------------------------------
with tab_dashboard:
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Cash Flow (current period)")
        cashflow, err = get("/api/cfo/cashflow")
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
        runway, err = get("/api/cfo/runway")
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
    forecast, err = get("/api/cfo/forecast")
    if err:
        st.error(f"Could not load forecast: {err}")
    elif forecast:
        forecast_df = pd.DataFrame(forecast["forecast"])
        if not forecast_df.empty:
            forecast_df["week_start"] = pd.to_datetime(forecast_df["week_start"])
            st.line_chart(forecast_df.set_index("week_start")["predicted_net_cashflow"])
        st.caption(forecast["explanation"])

        backtest = forecast.get("backtest", {})
        if backtest.get("comparison"):
            st.markdown("**Forecast backtest — predicted vs. actual (held-out weeks)**")
            bt_df = pd.DataFrame(backtest["comparison"])
            bt_df["week_start"] = pd.to_datetime(bt_df["week_start"])
            st.line_chart(bt_df.set_index("week_start")[["actual_net_cashflow", "predicted_net_cashflow"]])
            st.caption(f"Mean absolute error: {backtest['mean_absolute_error']:,.2f}")

    st.divider()

    st.subheader("Risk / Anomalies")
    risk, err = get("/api/cfo/risk")
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
                # Note: no org_id sent here at all — the question alone.
                # Node attaches the authenticated org_id server-side.
                result, err = post("/api/cfo/ask", {"question": question})
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
# Import Data tab — imports always land in the logged-in user's own
# organization. There is no org selector here anymore; the "create a new
# organization" flow that used to exist was removed because organization
# creation is now an admin-only, separate action (see SETUP.md for the
# bootstrap script) — mixing "upload my data" with "spin up a new tenant"
# in the same screen doesn't fit a real multi-tenant auth model.
# ---------------------------------------------------------------------------
with tab_import:
    st.subheader("Import your own transaction data")
    st.caption(
        f"Upload a CSV to add transactions to your organization (ID {user['organizationId']}). "
        "Required columns: date, amount, type (inflow/outflow), category. Description is optional."
    )

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

                st.warning(
                    f"This will add {len(valid_df)} transaction(s) to your organization "
                    f"(ID {user['organizationId']}). This does not overwrite existing data — it adds to it."
                )

                if st.button(f"Import {len(valid_df)} transactions", type="primary"):
                    progress = st.progress(0, text="Starting import...")
                    succeeded = 0
                    failed = []

                    for i, (_, row) in enumerate(valid_df.iterrows()):
                        # No org_id in this payload at all — Node derives it
                        # from the JWT. Even if something upstream injected
                        # one, routes/transactions.js on the server ignores it.
                        payload = {
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
