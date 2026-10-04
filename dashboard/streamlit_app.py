"""
FinPilot dashboard — Streamlit app. Talks ONLY to the Node API, never
directly to Postgres or the Python agent service (see README architecture).

Run with: streamlit run streamlit_app.py
Env vars:
  NODE_API_URL   Node API base URL (defaults to http://localhost:4000)
  DEMO_EMAIL     optional — together with DEMO_PASSWORD it enables the
  DEMO_PASSWORD  "Continue without login (demo)" button

Authentication: the user logs in, Node returns a JWT containing their
organization_id, and every request carries that JWT. The organization shown
is always the one the JWT says, never a value typed into a text box.
The demo button simply signs in to a dedicated demo account — the API
stays fully protected.
"""

import html
import os

import altair as alt
import pandas as pd
import requests
import streamlit as st

NODE_API_URL = os.getenv("NODE_API_URL", "http://localhost:4000").rstrip("/")
DEMO_EMAIL = os.getenv("DEMO_EMAIL")
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD")

# Palette
INK = "#14213D"
SLATE = "#5B6B82"
LINE = "#E3E9F0"
TEAL = "#0E9F8E"
CRIMSON = "#D6455D"
AMBER = "#E8A33D"
BLUE = "#2F5BEA"

st.set_page_config(
    page_title="FinPilot",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

STYLE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap');

.stApp, .stApp button, .stApp input, .stApp textarea { font-family: 'Manrope', system-ui, sans-serif; }
.stApp { background: #F3F6F9; color: #14213D; }
.block-container { padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1180px; }
header[data-testid="stHeader"] { background: transparent; }
[data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid #E3E9F0; }
div[data-testid="stVerticalBlockBorderWrapper"] { background: #FFFFFF; border-radius: 14px; }

button[data-baseweb="tab"] { font-weight: 600; }
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
  border-radius: 10px; font-weight: 600; border: 1px solid #D5DDE8;
}
.stFormSubmitButton > button, .stButton > button[kind="primary"] {
  background: #14213D; color: #FFFFFF; border-color: #14213D;
}

.brand { display: flex; align-items: center; gap: 10px; font-weight: 800; font-size: 1.25rem; letter-spacing: -0.02em; color: #14213D; }
.brand-mark { display: inline-flex; align-items: center; justify-content: center; width: 32px; height: 32px; border-radius: 9px; background: #14213D; color: #fff; font-size: 1rem; }

.login-title { font-size: 1.9rem; font-weight: 800; letter-spacing: -0.02em; margin: 28px 0 4px 0; color: #14213D; }
.login-sub { color: #5B6B82; margin-bottom: 18px; }

.usercard { border: 1px solid #E3E9F0; border-radius: 12px; padding: 12px 14px; margin: 14px 0 10px 0; background: #F8FAFC; }
.user-email { font-weight: 700; font-size: .92rem; word-break: break-all; }
.user-meta { color: #5B6B82; font-size: .8rem; margin-top: 2px; }

.page-title { font-size: 1.8rem; font-weight: 800; letter-spacing: -0.02em; margin-bottom: 2px; }
.page-sub { color: #5B6B82; margin-bottom: 20px; }

.hero { background: #14213D; color: #fff; border-radius: 14px; padding: 28px 32px; margin-bottom: 20px;
  display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.3fr); gap: 32px; align-items: center; }
.hero-label { font-size: .92rem; color: #A9B8D0; font-weight: 600; }
.hero-num { font-size: 3.6rem; font-weight: 800; line-height: 1.05; letter-spacing: -0.03em; font-variant-numeric: tabular-nums; }
.hero-num span { font-size: 1.1rem; font-weight: 600; color: #A9B8D0; margin-left: .4rem; letter-spacing: 0; }
.pill { display: inline-block; padding: 4px 12px; border-radius: 999px; font-size: .82rem; font-weight: 700; margin-top: 10px; color: #14213D; }
.track { height: 12px; background: rgba(255,255,255,.14); border-radius: 999px; overflow: hidden; }
.fill { height: 100%; border-radius: 999px; }
.ticks { display: flex; justify-content: space-between; color: #A9B8D0; font-size: .75rem; margin-top: 8px; }
.hero-note { color: #C9D5E8; font-size: .92rem; line-height: 1.55; margin-top: 16px; }
@media (max-width: 800px) { .hero { grid-template-columns: 1fr; gap: 20px; } .hero-num { font-size: 2.8rem; } }

.kpis { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); background: #fff; border: 1px solid #E3E9F0; border-radius: 14px; margin-bottom: 20px; }
.kpi { padding: 18px 24px; }
.kpi + .kpi { border-left: 1px solid #E3E9F0; }
.kpi-label { color: #5B6B82; font-size: .88rem; font-weight: 600; }
.kpi-value { font-size: 1.9rem; font-weight: 800; letter-spacing: -0.02em; font-variant-numeric: tabular-nums; }
@media (max-width: 700px) { .kpis { grid-template-columns: 1fr; } .kpi + .kpi { border-left: 0; border-top: 1px solid #E3E9F0; } }

.panel-title { font-weight: 700; font-size: 1.05rem; margin-bottom: 2px; }
.panel-sub { color: #5B6B82; font-size: .85rem; margin-bottom: 8px; }
</style>
"""
st.markdown(STYLE, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------
def auth_headers():
    token = st.session_state.get("token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def get(path, params=None):
    try:
        resp = requests.get(f"{NODE_API_URL}{path}", params=params, headers=auth_headers(), timeout=60)
        if resp.status_code == 401:
            _force_logout("Your session has expired. Please log in again.")
            return None, "Session expired"
        resp.raise_for_status()
        return resp.json(), None
    except requests.exceptions.RequestException as e:
        return None, str(e)


def post(path, json=None):
    try:
        resp = requests.post(f"{NODE_API_URL}{path}", json=json, headers=auth_headers(), timeout=90)
        if resp.status_code == 401:
            _force_logout("Your session has expired. Please log in again.")
            return None, "Session expired"
        resp.raise_for_status()
        return resp.json(), None
    except requests.exceptions.RequestException as e:
        return None, str(e)


def _force_logout(message):
    st.session_state.pop("token", None)
    st.session_state.pop("user", None)
    st.session_state.pop("is_demo", None)
    st.session_state["logout_message"] = message


def _login(email, password, demo=False):
    try:
        resp = requests.post(
            f"{NODE_API_URL}/api/auth/login",
            json={"email": email, "password": password},
            timeout=60,
        )
        if resp.status_code == 200:
            data = resp.json()
            st.session_state["token"] = data["token"]
            st.session_state["user"] = data["user"]
            st.session_state["is_demo"] = demo
            st.rerun()
        elif resp.status_code == 401:
            st.error("Wrong email or password. Check them and try again.")
        else:
            st.error(f"Login failed (HTTP {resp.status_code} from {NODE_API_URL}).")
    except requests.exceptions.RequestException as e:
        st.error(f"Couldn't reach the login service. It may still be waking up, so try again in a minute. ({e})")


BRAND_HTML = '<div class="brand"><span class="brand-mark">F</span>FinPilot</div>'


# ---------------------------------------------------------------------------
# Login gate — nothing below this renders until a valid JWT is in session
# ---------------------------------------------------------------------------
if "token" not in st.session_state:
    _, center, _ = st.columns([1, 1.3, 1])
    with center:
        st.markdown(BRAND_HTML, unsafe_allow_html=True)
        st.markdown('<div class="login-title">Welcome back</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="login-sub">Sign in to see your cash flow, runway and forecast.</div>',
            unsafe_allow_html=True,
        )

        if st.session_state.get("logout_message"):
            st.warning(st.session_state.pop("logout_message"))

        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log in")

        if submitted:
            _login(email.strip(), password)

        if DEMO_EMAIL and DEMO_PASSWORD:
            st.markdown("&nbsp;", unsafe_allow_html=True)
            st.caption("Just looking around? Explore with sample data. No account needed.")
            if st.button("Continue without login (demo)"):
                with st.spinner("Starting the demo. The first load can take a minute."):
                    _login(DEMO_EMAIL, DEMO_PASSWORD, demo=True)

        st.caption(
            "Need an account? Ask your organization's admin to register you, "
            "or see SETUP.md for how to bootstrap the first organization."
        )
    st.stop()  # nothing past this point runs until logged in


# ---------------------------------------------------------------------------
# Logged in — everything below runs with a valid JWT in session
# ---------------------------------------------------------------------------
user = st.session_state["user"]
is_demo = bool(st.session_state.get("is_demo")) or bool(
    DEMO_EMAIL and str(user["email"]).lower() == DEMO_EMAIL.lower()
)

with st.sidebar:
    st.markdown(BRAND_HTML, unsafe_allow_html=True)
    st.markdown(
        f'<div class="usercard"><div class="user-email">{html.escape(str(user["email"]))}</div>'
        f'<div class="user-meta">Organization {html.escape(str(user["organizationId"]))} · '
        f'{html.escape(str(user["role"]))}</div></div>',
        unsafe_allow_html=True,
    )
    if is_demo:
        st.caption("Demo mode: you're viewing sample data.")
    if st.button("Log out"):
        for key in ("token", "user", "is_demo", "chat_history"):
            st.session_state.pop(key, None)
        st.rerun()

st.markdown('<div class="page-title">Financial overview</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="page-sub">Based on your most recent transactions.</div>',
    unsafe_allow_html=True,
)

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


# ---------------------------------------------------------------------------
# Presentation helpers
# ---------------------------------------------------------------------------
RUNWAY_STATUS = {
    "critical": ("Critical", CRIMSON),
    "warning": ("Needs attention", AMBER),
    "healthy": ("Healthy", TEAL),
    "cashflow_positive": ("Cash-flow positive", TEAL),
}


def fmt(value) -> str:
    try:
        return f"{float(value):,.0f}"
    except (TypeError, ValueError):
        return "–"


def render_runway(runway: dict):
    label, color = RUNWAY_STATUS.get(runway.get("runway_status"), ("Unknown", SLATE))
    months = runway.get("runway_months")
    if months is None:
        big, unit, pct = "∞", "", 100
    else:
        months = float(months)
        big, unit, pct = f"{months:,.1f}", " months", max(2.0, min(100.0, months / 12 * 100))
    note = html.escape(str(runway.get("explanation", "")))
    st.markdown(
        '<div class="hero"><div>'
        '<div class="hero-label">Cash runway</div>'
        f'<div class="hero-num">{big}<span>{unit}</span></div>'
        f'<div class="pill" style="background:{color}">{label}</div>'
        '</div><div>'
        f'<div class="track"><div class="fill" style="width:{pct:.0f}%;background:{color}"></div></div>'
        '<div class="ticks"><span>0</span><span>6 months</span><span>12+ months</span></div>'
        f'<div class="hero-note">{note}</div>'
        '</div></div>',
        unsafe_allow_html=True,
    )


def render_kpis(cashflow: dict):
    net = cashflow.get("net_cashflow", 0)
    net_color = TEAL if (net or 0) >= 0 else CRIMSON
    st.markdown(
        '<div class="kpis">'
        f'<div class="kpi"><div class="kpi-label">Inflows</div><div class="kpi-value">{fmt(cashflow.get("inflows"))}</div></div>'
        f'<div class="kpi"><div class="kpi-label">Outflows</div><div class="kpi-value">{fmt(cashflow.get("outflows"))}</div></div>'
        f'<div class="kpi"><div class="kpi-label">Net cashflow</div><div class="kpi-value" style="color:{net_color}">{fmt(net)}</div></div>'
        '</div>',
        unsafe_allow_html=True,
    )


def panel_header(title: str, sub: str = ""):
    st.markdown(f'<div class="panel-title">{html.escape(title)}</div>', unsafe_allow_html=True)
    if sub:
        st.markdown(f'<div class="panel-sub">{html.escape(sub)}</div>', unsafe_allow_html=True)


def style_chart(chart):
    return (
        chart.properties(width="container", height=260)
        .configure_view(strokeWidth=0)
        .configure_axis(labelColor=SLATE, gridColor=LINE, domainColor=LINE, tickColor=LINE, labelFontSize=12)
        .configure_legend(labelColor=SLATE, title=None, orient="top")
    )


# A view switcher instead of st.tabs: Streamlit only pins st.chat_input to the
# bottom of the screen when it is called at the page root (not inside a tab),
# and a switcher tells us which view is active so the box only shows in chat.
VIEWS = ["Overview", "Ask the CFO"] + ([] if is_demo else ["Import data"])
view = (
    st.segmented_control("View", VIEWS, default=VIEWS[0], key="view", label_visibility="collapsed")
    or VIEWS[0]
)

# ---------------------------------------------------------------------------
# Overview — no org_id is sent anywhere. The Node API derives it entirely
# from the JWT in auth_headers().
# ---------------------------------------------------------------------------
if view == "Overview":
    if is_demo:
        st.info("You're exploring sample data in demo mode. Importing is turned off.")

    with st.spinner("Loading your numbers…"):
        cashflow, cf_err = get("/api/cfo/cashflow")
        runway, rw_err = get("/api/cfo/runway")
        forecast, fc_err = get("/api/cfo/forecast")
        risk, rk_err = get("/api/cfo/risk")

    if "token" not in st.session_state:  # a 401 forced a logout mid-load
        st.rerun()

    if rw_err:
        st.error(f"Couldn't load runway: {rw_err}")
    elif runway:
        render_runway(runway)

    if cf_err:
        st.error(f"Couldn't load cash flow: {cf_err}")
    elif cashflow:
        render_kpis(cashflow)

    left, right = st.columns(2)

    with left:
        with st.container(border=True):
            panel_header("Where the money goes", "Outflows by category, current period")
            by_cat = (cashflow or {}).get("outflow_by_category") or {}
            if by_cat:
                cat_df = pd.DataFrame(list(by_cat.items()), columns=["Category", "Amount"])
                chart = (
                    alt.Chart(cat_df)
                    .mark_bar(cornerRadiusEnd=5, color=CRIMSON)
                    .encode(
                        y=alt.Y("Category:N", sort="-x", title=None),
                        x=alt.X("Amount:Q", title=None, axis=alt.Axis(format="~s")),
                        tooltip=["Category", alt.Tooltip("Amount:Q", format=",.0f")],
                    )
                )
                st.altair_chart(style_chart(chart))
            elif not cf_err:
                st.caption("No outflows in this period yet.")
            if cashflow and cashflow.get("explanation"):
                st.caption(cashflow["explanation"])

    with right:
        with st.container(border=True):
            panel_header("Forecast", "Predicted net cashflow, next few weeks")
            if fc_err:
                st.error(f"Couldn't load forecast: {fc_err}")
            elif forecast:
                fdf = pd.DataFrame(forecast.get("forecast", []))
                if not fdf.empty:
                    fdf["week_start"] = pd.to_datetime(fdf["week_start"])
                    base = alt.Chart(fdf).encode(
                        x=alt.X("week_start:T", title=None, axis=alt.Axis(format="%b %d")),
                        y=alt.Y("predicted_net_cashflow:Q", title=None, axis=alt.Axis(format="~s")),
                        tooltip=[
                            alt.Tooltip("week_start:T", title="Week of", format="%b %d"),
                            alt.Tooltip("predicted_net_cashflow:Q", title="Predicted", format=",.0f"),
                        ],
                    )
                    area = base.mark_area(opacity=0.14, color=BLUE, line={"color": BLUE, "strokeWidth": 2.5})
                    zero = (
                        alt.Chart(pd.DataFrame({"y": [0]}))
                        .mark_rule(color=SLATE, strokeDash=[4, 4])
                        .encode(y="y:Q")
                    )
                    st.altair_chart(style_chart(area + zero))
                if forecast.get("explanation"):
                    st.caption(forecast["explanation"])

    backtest = (forecast or {}).get("backtest", {}) or {}
    if backtest.get("comparison"):
        with st.container(border=True):
            panel_header(
                "How accurate was the forecast?",
                "Predicted vs. actual for weeks the model hadn't seen",
            )
            bt = pd.DataFrame(backtest["comparison"])
            bt["week_start"] = pd.to_datetime(bt["week_start"])
            bt = bt.rename(columns={"actual_net_cashflow": "Actual", "predicted_net_cashflow": "Predicted"})
            long_bt = bt.melt(
                id_vars="week_start", value_vars=["Actual", "Predicted"], var_name="Series", value_name="Net cashflow"
            )
            chart = (
                alt.Chart(long_bt)
                .mark_line(point=True, strokeWidth=2.5)
                .encode(
                    x=alt.X("week_start:T", title=None, axis=alt.Axis(format="%b %d")),
                    y=alt.Y("Net cashflow:Q", title=None, axis=alt.Axis(format="~s")),
                    color=alt.Color("Series:N", scale=alt.Scale(domain=["Actual", "Predicted"], range=[INK, BLUE])),
                    tooltip=["Series", alt.Tooltip("Net cashflow:Q", format=",.0f")],
                )
            )
            st.altair_chart(style_chart(chart))
            mae = backtest.get("mean_absolute_error")
            if mae is not None:
                st.caption(f"Mean absolute error: {mae:,.2f}")

    with st.container(border=True):
        panel_header("Risks and anomalies", "Things worth a second look")
        if rk_err:
            st.error(f"Couldn't load risk data: {rk_err}")
        elif risk:
            if risk.get("explanation"):
                st.caption(risk["explanation"])
            spikes, gaps = risk.get("outflow_spikes") or [], risk.get("inflow_gaps") or []
            if spikes:
                st.markdown("**Unusual outflows**")
                st.dataframe(pd.DataFrame(spikes)[["date", "category", "amount", "reason"]], hide_index=True)
            if gaps:
                st.markdown("**Inflow gaps**")
                st.dataframe(
                    pd.DataFrame(gaps)[["month", "actual_inflow", "trailing_average_inflow", "reason"]],
                    hide_index=True,
                )
            if not spikes and not gaps:
                st.success("Nothing unusual found in this period.")

# ---------------------------------------------------------------------------
# Chat — st.chat_input sits at the page root, so it stays pinned to the bottom
# ---------------------------------------------------------------------------
STARTERS = [
    "How long is our runway?",
    "Where are we spending the most?",
    "What does the forecast look like?",
    "Anything risky I should know about?",
]

if view == "Ask the CFO":
    panel_header("Ask the CFO", "Ask in plain language. Answers come from your own transactions.")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    if not st.session_state.chat_history:
        cols = st.columns(len(STARTERS))
        for col, text in zip(cols, STARTERS):
            if col.button(text, key=f"starter_{text}"):
                st.session_state["pending_question"] = text
                st.rerun()

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            if msg["role"] == "assistant" and msg.get("agents_used"):
                st.caption(f"Used: {', '.join(msg['agents_used'])}. {msg.get('reasoning', '')}")

    question = st.chat_input("Ask about cash flow, runway, forecasts, or risk...")
    if not question:
        question = st.session_state.pop("pending_question", None)

    if question:
        st.session_state.chat_history.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.write(question)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                # No org_id sent: Node attaches the authenticated org_id server-side.
                result, err = post("/api/cfo/ask", {"question": question})
            if err:
                st.error(f"Couldn't reach the CFO agent: {err}")
            else:
                st.write(result["answer"])
                st.caption(f"Used: {', '.join(result['agents_used']) or 'none'}. {result['reasoning']}")
                st.session_state.chat_history.append(
                    {
                        "role": "assistant",
                        "content": result["answer"],
                        "agents_used": result["agents_used"],
                        "reasoning": result["reasoning"],
                    }
                )

# ---------------------------------------------------------------------------
# Import — hidden in demo mode. Imports always land in the logged-in
# user's own organization; Node ignores any org_id sent from here.
# ---------------------------------------------------------------------------
if view == "Import data":
    with st.container():
        panel_header(
            "Import transactions",
            f"Upload a CSV to add transactions to your organization (ID {user['organizationId']}).",
        )
        st.caption("Required columns: date, amount, type (inflow or outflow), category. Description is optional.")

        template_csv = (
            "date,amount,type,category,description\n"
            "2026-01-05,50000,inflow,revenue,Client payment\n"
            "2026-01-10,15000,outflow,rent,Office rent\n"
        )
        st.download_button("Download CSV template", template_csv, file_name="transactions_template.csv", mime="text/csv")

        uploaded_file = st.file_uploader("Choose a CSV file", type=["csv"])

        if uploaded_file is not None:
            try:
                raw_df = pd.read_csv(uploaded_file)
            except Exception as e:
                st.error(f"Couldn't read this file as a CSV: {e}")
                raw_df = None

            if raw_df is not None:
                valid_df, errors = validate_import_df(raw_df)

                st.write(f"**{len(valid_df)} of {len(raw_df)} rows are valid.**")

                if errors:
                    with st.expander(f"{len(errors)} row(s) will be skipped. See why"):
                        for e in errors:
                            st.text(e)

                if not valid_df.empty:
                    st.dataframe(valid_df.head(20), hide_index=True)
                    if len(valid_df) > 20:
                        st.caption(f"…and {len(valid_df) - 20} more rows")

                    st.warning(
                        f"This adds {len(valid_df)} transaction(s) to your organization "
                        f"(ID {user['organizationId']}). Existing data is not overwritten."
                    )

                    if st.button(f"Import {len(valid_df)} transactions", type="primary"):
                        progress = st.progress(0, text="Starting import...")
                        succeeded = 0
                        failed = []

                        for i, (_, row) in enumerate(valid_df.iterrows()):
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
                        st.success(f"Imported {succeeded} of {len(valid_df)} transactions.")
                        if failed:
                            with st.expander(f"{len(failed)} row(s) failed during import"):
                                for row_num, err in failed:
                                    st.text(f"Row {row_num}: {err}")