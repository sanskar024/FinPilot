"""
Runway Agent — how many months of cash remain at the current burn rate.

Deliberately does NOT hardcode an opening balance (that was the flaw in the
original FINTRO's compute.py). Instead, current balance is derived from the
full transaction history: sum(all inflows) - sum(all outflows) to date.
"""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from agents.cashflow_agent import compute_cashflow, fetch_transactions
from db.models import Transaction


def fetch_all_time_balance(session: Session, org_id: int) -> float:
    """Current cash balance = sum of every inflow minus every outflow ever recorded."""
    rows = session.query(Transaction).filter(Transaction.org_id == org_id).all()
    inflow = sum(float(r.amount) for r in rows if r.type == "inflow")
    outflow = sum(float(r.amount) for r in rows if r.type == "outflow")
    return round(inflow - outflow, 2)


def compute_runway(current_balance: float, monthly_burn_rate: float) -> dict:
    """
    Pure function: given a balance and a monthly burn rate, compute runway.

    If burn rate is zero or negative (business is cashflow-positive), runway
    is reported as infinite rather than a nonsensical number.
    """
    if monthly_burn_rate <= 0:
        return {
            "current_balance": round(current_balance, 2),
            "monthly_burn_rate": round(monthly_burn_rate, 2),
            "runway_months": None,
            "runway_status": "cashflow_positive",
        }

    runway_months = current_balance / monthly_burn_rate

    if runway_months < 2:
        status = "critical"
    elif runway_months < 6:
        status = "warning"
    else:
        status = "healthy"

    return {
        "current_balance": round(current_balance, 2),
        "monthly_burn_rate": round(monthly_burn_rate, 2),
        "runway_months": round(runway_months, 1),
        "runway_status": status,
    }


def explain_runway(result: dict) -> str:
    if result["runway_status"] == "cashflow_positive":
        return (
            f"Current balance is {result['current_balance']:,.2f} and outflows are not "
            f"exceeding inflows, so runway isn't a meaningful constraint right now."
        )
    status_phrase = {
        "critical": "This is a critical runway — action is needed soon.",
        "warning": "This is inside the danger zone — worth watching closely.",
        "healthy": "This is a comfortable runway.",
    }[result["runway_status"]]
    return (
        f"At the current balance of {result['current_balance']:,.2f} and a monthly burn "
        f"rate of {result['monthly_burn_rate']:,.2f}, the business has approximately "
        f"{result['runway_months']} months of runway remaining. {status_phrase}"
    )


def fetch_latest_transaction_date(session: Session, org_id: int) -> date:
    """
    The 'as of' date for runway calculations. Uses the most recent transaction
    date rather than the real wall-clock date, since seed/demo data is
    historical — using date.today() would look past the end of the data and
    find nothing.
    """
    latest = (
        session.query(Transaction.date)
        .filter(Transaction.org_id == org_id)
        .order_by(Transaction.date.desc())
        .first()
    )
    return latest[0] if latest else date.today()


def run_runway_agent(session: Session, org_id: int, lookback_days: int = 30) -> dict:
    """
    Full agent run: uses the last `lookback_days` of transactions (relative to
    the most recent transaction on record) to estimate the current burn rate,
    and the full history to get the current balance.
    """
    balance = fetch_all_time_balance(session, org_id)

    end = fetch_latest_transaction_date(session, org_id)
    start = end - timedelta(days=lookback_days)
    recent_txns = fetch_transactions(session, org_id, start, end)
    cashflow = compute_cashflow(recent_txns, period_days=lookback_days)

    result = compute_runway(balance, cashflow["monthly_burn_rate"])
    result["explanation"] = explain_runway(result)
    result["org_id"] = org_id
    result["based_on_period"] = f"{start.isoformat()} to {end.isoformat()}"
    return result
