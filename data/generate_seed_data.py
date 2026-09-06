"""
Generates a realistic 6-month synthetic transaction history for one small
business, and writes it to data/seed_transactions.csv.

Deliberately NOT random noise — it's built with a story so the agents built
later have something real to compute against:

  - Monthly recurring revenue (inflow) that grows slowly month over month
  - Recurring fixed costs (payroll, rent, software) as outflows
  - Variable costs (marketing, supplies) that fluctuate
  - Two deliberate anomalies: an unusually large one-off expense, and a
    month where an expected revenue payment is late — exactly what the
    Risk/Anomaly Agent (built later) should be able to flag
  - A gradual increase in burn rate in the final month, so the Runway
    Agent has a real "this is getting tighter" story to tell, not a
    flat, boring line

Run with: python generate_seed_data.py
"""

import csv
import random
from datetime import date, timedelta

random.seed(42)  # reproducible — same dataset every time this is run

START_DATE = date(2026, 3, 1)
NUM_MONTHS = 6
OUTPUT_PATH = "seed_transactions.csv"

rows = []


def add_row(d, amount, txn_type, category, description):
    rows.append(
        {
            "date": d.isoformat(),
            "amount": round(amount, 2),
            "type": txn_type,
            "category": category,
            "description": description,
        }
    )


def month_add(d: date, months: int) -> date:
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    return date(year, month, min(d.day, 28))


for m in range(NUM_MONTHS):
    month_start = month_add(START_DATE, m)
    is_last_month = m == NUM_MONTHS - 1

    # --- Recurring revenue (inflow) — grows ~4%/month, small day-jitter ---
    base_revenue = 900_000 * (1.04**m)
    if m == 3:
        # Anomaly #1: a major client payment arrives severely late.
        # Deliberately well under 50% of the trailing average revenue so the
        # Risk Agent's inflow-gap detector (threshold: <50% of trailing avg)
        # reliably catches it.
        add_row(
            month_add(month_start, 0).replace(day=25),
            base_revenue * 0.3,
            "inflow",
            "revenue",
            "Client invoice payment (partial, severely delayed)",
        )
    else:
        add_row(
            month_start.replace(day=5),
            base_revenue * 0.6,
            "inflow",
            "revenue",
            "Client invoice payment - Batch A",
        )
        add_row(
            month_start.replace(day=20),
            base_revenue * 0.4,
            "inflow",
            "revenue",
            "Client invoice payment - Batch B",
        )

    # --- Fixed recurring outflows ---
    payroll = 380_000 * (1.02**m)
    add_row(month_start.replace(day=1), payroll, "outflow", "payroll", "Monthly payroll run")

    rent = 60_000
    add_row(month_start.replace(day=2), rent, "outflow", "rent", "Office rent")

    software = 22_000 + random.uniform(-1500, 1500)
    add_row(month_start.replace(day=3), software, "outflow", "software", "SaaS subscriptions bundle")

    # --- Variable outflows: marketing + supplies, a few per month ---
    for _ in range(3):
        day = random.randint(6, 24)
        add_row(
            month_start.replace(day=day),
            random.uniform(15_000, 45_000),
            "outflow",
            "marketing",
            "Ad spend / campaign cost",
        )

    add_row(
        month_start.replace(day=random.randint(6, 24)),
        random.uniform(8_000, 18_000),
        "outflow",
        "supplies",
        "Office & operational supplies",
    )

    # --- Anomaly #2: one-off large unplanned expense in month 5 ---
    if m == 4:
        add_row(
            month_start.replace(day=15),
            210_000,
            "outflow",
            "equipment",
            "Emergency server hardware replacement",
        )

    # --- Final month: burn creeps up (extra hire + higher marketing spend) ---
    if is_last_month:
        add_row(
            month_start.replace(day=10),
            95_000,
            "outflow",
            "payroll",
            "New hire - signing bonus + first partial month salary",
        )
        add_row(
            month_start.replace(day=18),
            60_000,
            "outflow",
            "marketing",
            "Increased ad spend push",
        )

rows.sort(key=lambda r: r["date"])

with open(OUTPUT_PATH, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["date", "amount", "type", "category", "description"])
    writer.writeheader()
    writer.writerows(rows)

total_in = sum(r["amount"] for r in rows if r["type"] == "inflow")
total_out = sum(r["amount"] for r in rows if r["type"] == "outflow")

print(f"Wrote {len(rows)} transactions to {OUTPUT_PATH}")
print(f"Total inflow:  {total_in:,.2f}")
print(f"Total outflow: {total_out:,.2f}")
print(f"Net:           {total_in - total_out:,.2f}")
