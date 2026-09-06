"""
Output schema guardrail — every agent's response is validated against a
Pydantic model before it's returned. Malformed output (wrong types, missing
fields, an agent bug that produces garbage) is rejected here rather than
silently passed through to Node/Streamlit/the user.
"""

from typing import Literal, Optional

from pydantic import BaseModel, field_validator


class CashflowResponse(BaseModel):
    org_id: int
    period_start: str
    period_end: str
    inflows: float
    outflows: float
    net_cashflow: float
    daily_burn_rate: float
    monthly_burn_rate: float
    outflow_by_category: dict[str, float]
    transaction_count: int
    explanation: str

    @field_validator("inflows", "outflows")
    @classmethod
    def non_negative(cls, v):
        if v < 0:
            raise ValueError("inflows/outflows cannot be negative")
        return v


class RunwayResponse(BaseModel):
    org_id: int
    current_balance: float
    monthly_burn_rate: float
    runway_months: Optional[float]
    runway_status: Literal["critical", "warning", "healthy", "cashflow_positive"]
    explanation: str
    based_on_period: str


class ForecastWeek(BaseModel):
    week_start: str
    predicted_net_cashflow: float


class ForecastResponse(BaseModel):
    org_id: int
    forecast: list[ForecastWeek]
    backtest: dict
    explanation: str


class RiskResponse(BaseModel):
    org_id: int
    outflow_spikes: list[dict]
    inflow_gaps: list[dict]
    explanation: str


class ChatResponse(BaseModel):
    """
    The CFO Chat Agent's output. agents_used + reasoning make the agent's
    decision-making visible instead of a black box (README point #3).
    """

    answer: str
    agents_used: list[str]
    reasoning: str
    is_fallback: bool = False  # true if guardrails blocked the question or the LLM call failed


def validate_output(model_cls: type[BaseModel], data: dict) -> dict:
    """
    Validates `data` against `model_cls`. Raises pydantic.ValidationError on
    failure — callers (the FastAPI route handlers) should let this surface
    as a 500 rather than silently returning bad data, since a validation
    failure here means an agent produced something it shouldn't have.
    """
    validated = model_cls(**data)
    return validated.model_dump()
