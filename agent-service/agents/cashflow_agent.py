"""
Cashflow Agent — computes inflows, outflows, net cashflow, and burn rate
for an organization over a date range.

Follows fetch -> compute -> explain, and compute_cashflow() is a pure
function (list of dicts in, dict out) so it's testable without a database.
"""

from datetime import date
from typing import Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from db.models import Transaction


def fetch_transactions(session: Session, org_id: int, start: date, end: date) -> list[dict]:
    """Pulls raw transaction rows for the org/date range and converts to plain dicts."""
    rows = (
        session.query(Transaction)
        .filter(
            and_(
                Transaction.org_id == org_id,
                Transaction.date >= start,
                Transaction.date <= end,
            )
        )
        .order_by(Transaction.date)
        .all()
    )
    return [r.as_dict() for r in rows]


def compute_cashflow(transactions: list[dict], period_days: Optional[int] = None) -> dict:
    """
    Pure function: given a list of transaction dicts, compute cashflow metrics.

    period_days: number of days the transactions span. If not given, it's
    inferred from period_days = 30 as a fallback so burn_rate is never a
    divide-by-zero — but callers should pass the real period length.
    """
    inflows = sum(t["amount"] for t in transactions if t["type"] == "inflow")
    outflows = sum(t["amount"] for t in transactions if t["type"] == "outflow")
    net = inflows - outflows

    days = period_days if period_days and period_days > 0 else 30
    daily_burn = outflows / days
    monthly_burn = daily_burn * 30

    by_category = {}
    for t in transactions:
        if t["type"] == "outflow":
            by_category[t["category"]] = by_category.get(t["category"], 0) + t["amount"]

    return {
        "inflows": round(inflows, 2),
        "outflows": round(outflows, 2),
        "net_cashflow": round(net, 2),
        "daily_burn_rate": round(daily_burn, 2),
        "monthly_burn_rate": round(monthly_burn, 2),
        "outflow_by_category": {k: round(v, 2) for k, v in by_category.items()},
        "transaction_count": len(transactions),
    }


def explain_cashflow(result: dict, start: date, end: date) -> str:
    """Plain-English summary of the computed numbers."""
    net_word = "positive" if result["net_cashflow"] >= 0 else "negative"
    top_category = (
        max(result["outflow_by_category"], key=result["outflow_by_category"].get)
        if result["outflow_by_category"]
        else None
    )
    explanation = (
        f"Between {start} and {end}, inflows totaled {result['inflows']:,.2f} and "
        f"outflows totaled {result['outflows']:,.2f}, for a {net_word} net cashflow of "
        f"{result['net_cashflow']:,.2f}. Monthly burn rate is approximately "
        f"{result['monthly_burn_rate']:,.2f}."
    )
    if top_category:
        explanation += f" The largest outflow category was '{top_category}'."
    return explanation


def run_cashflow_agent(session: Session, org_id: int, start: date, end: date) -> dict:
    """Full agent run: fetch -> compute -> explain."""
    transactions = fetch_transactions(session, org_id, start, end)
    period_days = (end - start).days + 1
    result = compute_cashflow(transactions, period_days=period_days)
    result["explanation"] = explain_cashflow(result, start, end)
    result["period_start"] = start.isoformat()
    result["period_end"] = end.isoformat()
    result["org_id"] = org_id
    return result
