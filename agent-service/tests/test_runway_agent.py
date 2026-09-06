import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.runway_agent import compute_runway


def test_runway_healthy():
    result = compute_runway(current_balance=1_000_000, monthly_burn_rate=100_000)
    assert result["runway_months"] == 10.0
    assert result["runway_status"] == "healthy"


def test_runway_warning():
    result = compute_runway(current_balance=300_000, monthly_burn_rate=100_000)
    assert result["runway_months"] == 3.0
    assert result["runway_status"] == "warning"


def test_runway_critical():
    result = compute_runway(current_balance=100_000, monthly_burn_rate=100_000)
    assert result["runway_months"] == 1.0
    assert result["runway_status"] == "critical"


def test_runway_cashflow_positive_when_burn_is_zero_or_negative():
    result = compute_runway(current_balance=500_000, monthly_burn_rate=0)
    assert result["runway_status"] == "cashflow_positive"
    assert result["runway_months"] is None

    result_negative_burn = compute_runway(current_balance=500_000, monthly_burn_rate=-50_000)
    assert result_negative_burn["runway_status"] == "cashflow_positive"
