"""
FastAPI entry point — exposes the 5 agents over HTTP.

Only the Node API should ever call this service (see ALLOWED_ORIGINS in
.env) — Streamlit talks to Node, Node talks here. This keeps one clear
entry point into the whole system.
"""

import os
from datetime import date

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from agents.cashflow_agent import run_cashflow_agent
from agents.cfo_chat_agent import run_cfo_chat_agent
from agents.forecast_agent import run_forecast_agent
from agents.risk_agent import run_risk_agent
from agents.runway_agent import fetch_latest_transaction_date, run_runway_agent
from db.session import get_session
from guardrails.output_schema import (
    CashflowResponse,
    ChatResponse,
    ForecastResponse,
    RiskResponse,
    RunwayResponse,
    validate_output,
)

load_dotenv()

app = FastAPI(title="FinPilot Agent Service")

allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:4000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    org_id: int
    question: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/cashflow")
def cashflow(
    org_id: int,
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    session: Session = Depends(get_session),
):
    if end is None:
        end = fetch_latest_transaction_date(session, org_id)
    if start is None:
        start = end.replace(day=1)

    result = run_cashflow_agent(session, org_id, start, end)
    return validate_output(CashflowResponse, result)


@app.get("/runway")
def runway(org_id: int, session: Session = Depends(get_session)):
    result = run_runway_agent(session, org_id)
    return validate_output(RunwayResponse, result)


@app.get("/forecast")
def forecast(org_id: int, weeks_ahead: int = 6, session: Session = Depends(get_session)):
    result = run_forecast_agent(session, org_id, weeks_ahead=weeks_ahead)
    return validate_output(ForecastResponse, result)


@app.get("/risk")
def risk(org_id: int, session: Session = Depends(get_session)):
    result = run_risk_agent(session, org_id)
    return validate_output(RiskResponse, result)


@app.post("/chat")
def chat(request: ChatRequest, session: Session = Depends(get_session)):
    try:
        return run_cfo_chat_agent(session, request.org_id, request.question)
    except Exception as e:
        # An unexpected agent failure should surface as a clear 500, not a
        # half-formed or fabricated answer — this is part of the
        # hallucination guardrail too.
        raise HTTPException(status_code=500, detail=f"Chat agent failed: {str(e)}")
