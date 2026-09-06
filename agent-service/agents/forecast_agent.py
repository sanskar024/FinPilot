"""
Forecast Agent — projects future weekly net cashflow using a simple,
explainable linear trend over weekly aggregates (no black-box model, so
every number in the forecast can be traced back to arithmetic you can
check by hand).

Includes backtest_forecast(): holds out the last `holdout_weeks` of real
data, forecasts them using only the earlier weeks, and compares predicted
vs. actual. This is what proves the forecast isn't just a guess.
"""

from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy.orm import Session

from db.models import Transaction


def fetch_all_transactions(session: Session, org_id: int) -> list[dict]:
    rows = (
        session.query(Transaction)
        .filter(Transaction.org_id == org_id)
        .order_by(Transaction.date)
        .all()
    )
    return [r.as_dict() for r in rows]


def _weekly_net(transactions: list[dict]) -> list[tuple[date, float]]:
    """Buckets transactions into ISO weeks and returns (week_start, net_cashflow) sorted by week."""
    weekly = defaultdict(float)
    for t in transactions:
        d = t["date"]
        week_start = d - timedelta(days=d.weekday())  # Monday of that week
        signed = t["amount"] if t["type"] == "inflow" else -t["amount"]
        weekly[week_start] += signed
    return sorted(weekly.items())


def _linear_trend(values: list[float]) -> tuple[float, float]:
    """
    Fits y = slope*x + intercept via simple least squares, no numpy required.
    Returns (slope, intercept).
    """
    n = len(values)
    if n < 2:
        return 0.0, (values[0] if values else 0.0)

    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(values) / n

    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, values))
    denominator = sum((x - mean_x) ** 2 for x in xs)

    slope = numerator / denominator if denominator else 0.0
    intercept = mean_y - slope * mean_x
    return slope, intercept


def forecast_weekly_net(weekly_series: list[tuple[date, float]], weeks_ahead: int) -> list[dict]:
    """
    Pure function: given historical (week_start, net) pairs, project
    `weeks_ahead` future weeks using a linear trend fit to the history.
    """
    if not weekly_series:
        return []

    values = [v for _, v in weekly_series]
    slope, intercept = _linear_trend(values)

    last_week_start = weekly_series[-1][0]
    n = len(values)

    forecast = []
    for i in range(1, weeks_ahead + 1):
        week_start = last_week_start + timedelta(weeks=i)
        predicted = intercept + slope * (n - 1 + i)
        forecast.append({"week_start": week_start.isoformat(), "predicted_net_cashflow": round(predicted, 2)})
    return forecast


def backtest_forecast(transactions: list[dict], holdout_weeks: int = 2) -> dict:
    """
    Holds out the last `holdout_weeks` of real weekly data, fits the trend
    on everything before that, forecasts the held-out weeks, and compares
    predicted vs. actual so forecast accuracy is measurable, not assumed.
    """
    weekly_series = _weekly_net(transactions)

    if len(weekly_series) <= holdout_weeks:
        return {"error": "Not enough weekly history to backtest with this holdout size."}

    train = weekly_series[:-holdout_weeks]
    actual_holdout = weekly_series[-holdout_weeks:]

    predicted = forecast_weekly_net(train, weeks_ahead=holdout_weeks)

    comparison = []
    abs_errors = []
    for (actual_week, actual_val), pred in zip(actual_holdout, predicted):
        error = pred["predicted_net_cashflow"] - actual_val
        abs_errors.append(abs(error))
        comparison.append(
            {
                "week_start": actual_week.isoformat(),
                "actual_net_cashflow": round(actual_val, 2),
                "predicted_net_cashflow": pred["predicted_net_cashflow"],
                "error": round(error, 2),
            }
        )

    mean_abs_error = sum(abs_errors) / len(abs_errors) if abs_errors else None

    return {
        "holdout_weeks": holdout_weeks,
        "comparison": comparison,
        "mean_absolute_error": round(mean_abs_error, 2) if mean_abs_error is not None else None,
    }


def explain_forecast(forecast: list[dict], backtest: dict) -> str:
    if not forecast:
        return "Not enough transaction history yet to produce a forecast."

    direction = "improving" if forecast[-1]["predicted_net_cashflow"] > forecast[0]["predicted_net_cashflow"] else "declining"
    text = (
        f"Based on the linear trend in weekly net cashflow, the next {len(forecast)} "
        f"week(s) are projected to show a {direction} trend, ending at approximately "
        f"{forecast[-1]['predicted_net_cashflow']:,.2f} net cashflow per week."
    )
    if backtest.get("mean_absolute_error") is not None:
        text += (
            f" A backtest against the last {backtest['holdout_weeks']} actual week(s) of data "
            f"gave a mean absolute error of {backtest['mean_absolute_error']:,.2f}, so treat this "
            f"forecast as directionally useful, not exact."
        )
    return text


def run_forecast_agent(session: Session, org_id: int, weeks_ahead: int = 6, backtest_holdout_weeks: int = 2) -> dict:
    transactions = fetch_all_transactions(session, org_id)
    weekly_series = _weekly_net(transactions)

    forecast = forecast_weekly_net(weekly_series, weeks_ahead)
    backtest = backtest_forecast(transactions, holdout_weeks=backtest_holdout_weeks)

    return {
        "org_id": org_id,
        "forecast": forecast,
        "backtest": backtest,
        "explanation": explain_forecast(forecast, backtest),
    }
