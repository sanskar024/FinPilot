import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date

from agents.risk_agent import detect_outflow_spikes, detect_inflow_gaps


def _txn(d, amount, txn_type, category, id_, description=""):
    return {"id": id_, "date": d, "amount": amount, "type": txn_type, "category": category, "description": description}


def test_detect_outflow_spikes_flags_category_outlier():
    transactions = [
        _txn(date(2026, 1, 1), 100, "outflow", "marketing", 1),
        _txn(date(2026, 1, 8), 102, "outflow", "marketing", 2),
        _txn(date(2026, 1, 15), 98, "outflow", "marketing", 3),
        _txn(date(2026, 1, 22), 101, "outflow", "marketing", 4),
        _txn(date(2026, 1, 29), 99, "outflow", "marketing", 5),
        _txn(date(2026, 2, 5), 103, "outflow", "marketing", 6),
        _txn(date(2026, 2, 12), 2000, "outflow", "marketing", 7),  # clear outlier
    ]
    flagged = detect_outflow_spikes(transactions)

    assert len(flagged) == 1
    assert flagged[0]["amount"] == 2000
    assert flagged[0]["detection_method"] == "category_z_score"


def test_detect_outflow_spikes_ignores_sparse_category_without_global_outlier():
    # Only 1 transaction in "equipment" — not enough for z-score, and not
    # large enough relative to the rest to trip the global check either.
    transactions = [
        _txn(date(2026, 1, 1), 100, "outflow", "software", 1),
        _txn(date(2026, 1, 8), 110, "outflow", "software", 2),
        _txn(date(2026, 1, 15), 90, "outflow", "software", 3),
        _txn(date(2026, 1, 22), 120, "outflow", "equipment", 4),
    ]
    flagged = detect_outflow_spikes(transactions)
    assert len(flagged) == 0


def test_detect_outflow_spikes_catches_global_outlier_in_sparse_category():
    transactions = [
        _txn(date(2026, 1, 1), 100, "outflow", "software", 1),
        _txn(date(2026, 1, 8), 110, "outflow", "software", 2),
        _txn(date(2026, 1, 15), 90, "outflow", "software", 3),
        _txn(date(2026, 1, 22), 105, "outflow", "software", 4),
        _txn(date(2026, 1, 29), 95, "outflow", "software", 5),
        _txn(date(2026, 2, 1), 10_000, "outflow", "equipment", 6),  # huge one-off
    ]
    flagged = detect_outflow_spikes(transactions)

    assert len(flagged) == 1
    assert flagged[0]["detection_method"] == "global_outlier"
    assert flagged[0]["category"] == "equipment"


def test_detect_inflow_gaps_flags_severe_drop():
    transactions = [
        _txn(date(2026, 1, 5), 1000, "inflow", "revenue", 1),
        _txn(date(2026, 2, 5), 1000, "inflow", "revenue", 2),
        _txn(date(2026, 3, 5), 1000, "inflow", "revenue", 3),
        _txn(date(2026, 4, 5), 200, "inflow", "revenue", 4),  # severe drop
    ]
    flagged = detect_inflow_gaps(transactions)

    assert len(flagged) == 1
    assert flagged[0]["month"] == "2026-04"


def test_detect_inflow_gaps_no_flag_for_normal_variation():
    transactions = [
        _txn(date(2026, 1, 5), 1000, "inflow", "revenue", 1),
        _txn(date(2026, 2, 5), 950, "inflow", "revenue", 2),
        _txn(date(2026, 3, 5), 1050, "inflow", "revenue", 3),
    ]
    flagged = detect_inflow_gaps(transactions)
    assert len(flagged) == 0
