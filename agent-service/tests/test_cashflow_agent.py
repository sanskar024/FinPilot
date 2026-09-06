"""
Tests for the Cashflow Agent's pure compute function. No database needed —
that's the point of separating fetch/compute/explain.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date

from agents.cashflow_agent import compute_cashflow, explain_cashflow


def test_compute_cashflow_basic_totals():
    transactions = [
        {"amount": 1000, "type": "inflow", "category": "revenue"},
        {"amount": 300, "type": "outflow", "category": "rent"},
        {"amount": 200, "type": "outflow", "category": "software"},
    ]
    result = compute_cashflow(transactions, period_days=30)

    assert result["inflows"] == 1000
    assert result["outflows"] == 500
    assert result["net_cashflow"] == 500


def test_compute_cashflow_burn_rate_scales_with_period():
    transactions = [{"amount": 300, "type": "outflow", "category": "rent"}]

    result_30_days = compute_cashflow(transactions, period_days=30)
    result_15_days = compute_cashflow(transactions, period_days=15)

    # Same total outflow over half the period => double the daily burn rate
    assert result_15_days["daily_burn_rate"] == result_30_days["daily_burn_rate"] * 2


def test_compute_cashflow_empty_transactions():
    result = compute_cashflow([], period_days=30)

    assert result["inflows"] == 0
    assert result["outflows"] == 0
    assert result["net_cashflow"] == 0
    assert result["transaction_count"] == 0


def test_compute_cashflow_category_breakdown():
    transactions = [
        {"amount": 100, "type": "outflow", "category": "rent"},
        {"amount": 50, "type": "outflow", "category": "rent"},
        {"amount": 30, "type": "outflow", "category": "software"},
    ]
    result = compute_cashflow(transactions, period_days=30)

    assert result["outflow_by_category"]["rent"] == 150
    assert result["outflow_by_category"]["software"] == 30


def test_explain_cashflow_mentions_top_category():
    transactions = [
        {"amount": 500, "type": "outflow", "category": "payroll"},
        {"amount": 50, "type": "outflow", "category": "software"},
    ]
    result = compute_cashflow(transactions, period_days=30)
    explanation = explain_cashflow(result, date(2026, 1, 1), date(2026, 1, 31))

    assert "payroll" in explanation
