"""
Risk / Anomaly Agent — flags unusual transactions using simple, explainable
statistics (z-scores), not a black-box anomaly-detection model. Two kinds
of anomalies are checked:

  1. Outflow spikes: any single transaction whose amount is an outlier
     relative to that category's normal spend (z-score threshold)
  2. Missing expected inflow: a month where inflow drops sharply compared
     to the trailing average, which can indicate a late or missing payment
"""

import statistics
from collections import defaultdict

from sqlalchemy.orm import Session

from db.models import Transaction

Z_SCORE_THRESHOLD = 2.0  # transactions beyond this many std-devs are flagged
GLOBAL_OUTLIER_MULTIPLIER = 3.0  # flag any outflow > 3x the overall median outflow
INFLOW_DROP_THRESHOLD = 0.5  # flag if a month's inflow is <50% of trailing average


def fetch_all_transactions(session: Session, org_id: int) -> list[dict]:
    rows = (
        session.query(Transaction)
        .filter(Transaction.org_id == org_id)
        .order_by(Transaction.date)
        .all()
    )
    return [r.as_dict() for r in rows]


def detect_outflow_spikes(transactions: list[dict]) -> list[dict]:
    """
    Pure function. Two passes:
      1. Category-based z-score: flags a transaction that's unusual relative
         to its own category's history (needs >=3 prior transactions in
         that category to judge "unusual").
      2. Global outlier check: flags any outflow far above the overall
         median outflow, regardless of category — catches one-off large
         expenses in categories with too little history for a z-score
         (e.g. a single big equipment purchase).
    """
    flagged = []
    flagged_ids = set()
    sparse_categories = set()  # categories with <3 txns — z-score can't judge these

    # --- Pass 1: category-based z-score ---
    by_category = defaultdict(list)
    for t in transactions:
        if t["type"] == "outflow":
            by_category[t["category"]].append(t)

    for category, txns in by_category.items():
        amounts = [t["amount"] for t in txns]
        if len(amounts) < 3:
            sparse_categories.add(category)
            continue  # not enough history in this category to judge "unusual"
        mean = statistics.mean(amounts)
        stdev = statistics.stdev(amounts)
        if stdev == 0:
            continue
        for t in txns:
            z = (t["amount"] - mean) / stdev
            if z > Z_SCORE_THRESHOLD:
                flagged.append(
                    {
                        "date": t["date"].isoformat(),
                        "category": category,
                        "amount": t["amount"],
                        "detection_method": "category_z_score",
                        "z_score": round(z, 2),
                        "description": t["description"],
                        "reason": f"'{category}' spend of {t['amount']:,.2f} is {round(z, 1)} std-devs above the usual {mean:,.2f}",
                    }
                )
                flagged_ids.add(t["id"])

    # --- Pass 2: global outlier check, ONLY for categories too sparse for pass 1 ---
    # (a large but consistent recurring expense like payroll already went through
    # pass 1 and is correctly judged "normal for itself" — this pass exists purely
    # to catch one-off expenses in categories with too little history, like a
    # single big equipment purchase)
    all_outflow_amounts = [t["amount"] for t in transactions if t["type"] == "outflow"]
    if len(all_outflow_amounts) >= 5:
        median = statistics.median(all_outflow_amounts)
        for t in transactions:
            if t["type"] != "outflow" or t["category"] not in sparse_categories:
                continue
            if t["id"] in flagged_ids:
                continue
            if median > 0 and t["amount"] > median * GLOBAL_OUTLIER_MULTIPLIER:
                flagged.append(
                    {
                        "date": t["date"].isoformat(),
                        "category": t["category"],
                        "amount": t["amount"],
                        "detection_method": "global_outlier",
                        "median_outflow": round(median, 2),
                        "description": t["description"],
                        "reason": (
                            f"One-off '{t['category']}' expense of {t['amount']:,.2f} is "
                            f"{round(t['amount'] / median, 1)}x the typical outflow of {median:,.2f}"
                        ),
                    }
                )
                flagged_ids.add(t["id"])

    return flagged


def detect_inflow_gaps(transactions: list[dict]) -> list[dict]:
    """
    Pure function. Buckets inflows by calendar month, and flags any month
    whose total inflow drops below INFLOW_DROP_THRESHOLD of the trailing
    average of prior months — a signal of a late or missing payment.
    """
    monthly = defaultdict(float)
    for t in transactions:
        if t["type"] == "inflow":
            key = t["date"].strftime("%Y-%m")
            monthly[key] += t["amount"]

    months = sorted(monthly.keys())
    flagged = []
    for i, month in enumerate(months):
        if i == 0:
            continue
        prior_months = months[:i]
        trailing_avg = sum(monthly[m] for m in prior_months) / len(prior_months)
        if trailing_avg > 0 and monthly[month] < trailing_avg * INFLOW_DROP_THRESHOLD:
            flagged.append(
                {
                    "month": month,
                    "actual_inflow": round(monthly[month], 2),
                    "trailing_average_inflow": round(trailing_avg, 2),
                    "reason": (
                        f"Inflow in {month} was {monthly[month]:,.2f}, only "
                        f"{round(monthly[month] / trailing_avg * 100)}% of the trailing "
                        f"average of {trailing_avg:,.2f} — check for a late or missing payment."
                    ),
                }
            )
    return flagged


def explain_risk(spikes: list[dict], gaps: list[dict]) -> str:
    if not spikes and not gaps:
        return "No significant anomalies detected in outflow spending or inflow timing."
    parts = []
    if spikes:
        parts.append(f"{len(spikes)} unusual outflow(s) flagged")
    if gaps:
        parts.append(f"{len(gaps)} month(s) with a suspicious inflow gap")
    return "Flagged: " + "; ".join(parts) + "."


def run_risk_agent(session: Session, org_id: int) -> dict:
    transactions = fetch_all_transactions(session, org_id)
    spikes = detect_outflow_spikes(transactions)
    gaps = detect_inflow_gaps(transactions)
    return {
        "org_id": org_id,
        "outflow_spikes": spikes,
        "inflow_gaps": gaps,
        "explanation": explain_risk(spikes, gaps),
    }
