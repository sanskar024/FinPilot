"""
CFO Chat Agent — the orchestrator and "front door" of the system.

Flow (a real LangGraph StateGraph, not just sequential function calls):

    guardrail_check -> [blocked] -> respond_blocked -> END
                     -> [allowed] -> route -> call_agents -> synthesize -> validate -> END

Design choices worth explaining in an interview:
  - Routing is keyword-based, not another LLM call — deterministic and
    testable, and it's what the eval suite checks against a golden set.
  - Guardrails run BEFORE any agent or LLM call, not after — a blocked
    question never reaches the LLM or touches the database.
  - The LLM synthesis step is optional: if no ANTHROPIC_API_KEY is set (or
    the call fails), it falls back to a template built from each called
    agent's own `explanation` field. The system degrades gracefully instead
    of crashing or hallucinating — the hallucination guardrail.
  - agents_used + reasoning are always returned alongside the answer, so
    the routing decision is visible, not a black box.
"""

import os
from datetime import date
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from agents.cashflow_agent import run_cashflow_agent
from agents.risk_agent import run_risk_agent
from agents.runway_agent import run_runway_agent, fetch_latest_transaction_date
from agents.forecast_agent import run_forecast_agent
from guardrails.input_sanitizer import sanitize_input
from guardrails.output_schema import ChatResponse, validate_output
from guardrails.scope_check import scope_check

ROUTING_KEYWORDS = {
    "cashflow": {"cash flow", "cashflow", "burn", "inflow", "outflow", "spend", "spending", "spent", "expense", "expenses"},
    "runway": {"runway", "afford", "hire", "hiring", "how long", "months of cash", "run out"},
    "forecast": {"forecast", "projection", "project", "predict", "future", "next month", "next week", "next few weeks"},
    "risk": {"risk", "anomaly", "anomalies", "unusual", "suspicious", "spike", "weird", "transaction", "transactions"},
}


class ChatState(TypedDict, total=False):
    org_id: int
    question: str
    blocked: bool
    block_reason: str
    agents_used: list[str]
    agent_results: dict
    answer: str
    reasoning: str
    is_fallback: bool


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------


def guardrail_check(state: ChatState) -> ChatState:
    sanitized = sanitize_input(state["question"])
    if not sanitized["safe"]:
        return {**state, "blocked": True, "block_reason": sanitized["reason"]}

    scope = scope_check(sanitized["cleaned"])
    if not scope["allowed"]:
        return {**state, "blocked": True, "block_reason": scope["reason"]}

    return {**state, "question": sanitized["cleaned"], "blocked": False}


def route(state: ChatState) -> ChatState:
    """Pure-ish routing decision — kept as a node so the graph shows the step explicitly."""
    lowered = state["question"].lower()
    matched = [name for name, keywords in ROUTING_KEYWORDS.items() if any(k in lowered for k in keywords)]

    if not matched:
        # No specific signal — give a general overview rather than guessing.
        matched = ["cashflow", "runway"]

    return {**state, "agents_used": matched}


def call_agents(state: ChatState, session: Session) -> ChatState:
    results = {}
    # Anchor on the most recent transaction date, not the real wall-clock
    # date — this is historical/demo data, not a live feed.
    as_of = fetch_latest_transaction_date(session, state["org_id"])

    if "cashflow" in state["agents_used"]:
        results["cashflow"] = run_cashflow_agent(session, state["org_id"], start=as_of.replace(day=1), end=as_of)
    if "runway" in state["agents_used"]:
        results["runway"] = run_runway_agent(session, state["org_id"])
    if "forecast" in state["agents_used"]:
        results["forecast"] = run_forecast_agent(session, state["org_id"])
    if "risk" in state["agents_used"]:
        results["risk"] = run_risk_agent(session, state["org_id"])

    return {**state, "agent_results": results}


def _template_synthesis(state: ChatState) -> str:
    """Fallback answer built from the agents' own explanations — used when
    no LLM is configured, or the LLM call fails. Never invents a number."""
    explanations = [r["explanation"] for r in state["agent_results"].values() if "explanation" in r]
    return " ".join(explanations) if explanations else "No data was available to answer this question."


def _llm_synthesis(state: ChatState) -> str | None:
    """
    Attempts to use Gemini to turn the agents' structured output into a more
    natural answer to the specific question asked. Returns None on any
    failure so the caller falls back cleanly — this IS the hallucination
    guardrail: no API key or a failed call means no made-up answer, just
    the safe template instead.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")

        prompt = (
            "You are a CFO copilot. Answer the user's question using ONLY the data below. "
            "Do not invent any numbers not present in the data. Frame any suggestions as "
            "options with reasoning, not directives.\n\n"
            f"Question: {state['question']}\n\n"
            f"Data: {state['agent_results']}\n"
        )
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Gemini call failed: {e}")
        return None
    
def synthesize(state: ChatState) -> ChatState:
    llm_answer = _llm_synthesis(state)
    if llm_answer:
        return {
            **state,
            "answer": llm_answer,
            "reasoning": f"Called {', '.join(state['agents_used'])} agent(s) based on the question, then used an LLM to phrase the answer.",
            "is_fallback": False,
        }

    template_answer = _template_synthesis(state)
    return {
        **state,
        "answer": template_answer,
        "reasoning": f"Called {', '.join(state['agents_used'])} agent(s) based on the question; no LLM configured, so this is a direct summary of their output.",
        "is_fallback": True,
    }


def respond_blocked(state: ChatState) -> ChatState:
    return {
        **state,
        "agents_used": [],
        "answer": state["block_reason"],
        "reasoning": "Blocked by a guardrail before any agent was called.",
        "is_fallback": True,
    }


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------


def build_graph(session: Session):
    """
    Builds the LangGraph StateGraph. Takes a session because call_agents
    needs DB access — bound via a closure so the graph's nodes stay
    simple functions of state.
    """
    graph = StateGraph(ChatState)

    graph.add_node("guardrail_check", guardrail_check)
    graph.add_node("route", route)
    graph.add_node("call_agents", lambda state: call_agents(state, session))
    graph.add_node("synthesize", synthesize)
    graph.add_node("respond_blocked", respond_blocked)

    graph.add_edge(START, "guardrail_check")
    graph.add_conditional_edges(
        "guardrail_check",
        lambda state: "blocked" if state["blocked"] else "allowed",
        {"blocked": "respond_blocked", "allowed": "route"},
    )
    graph.add_edge("route", "call_agents")
    graph.add_edge("call_agents", "synthesize")
    graph.add_edge("synthesize", END)
    graph.add_edge("respond_blocked", END)

    return graph.compile()


def run_cfo_chat_agent(session: Session, org_id: int, question: str) -> dict:
    """Full agent run: builds the graph, runs it, validates the output."""
    app = build_graph(session)
    final_state = app.invoke({"org_id": org_id, "question": question})

    result = {
        "answer": final_state["answer"],
        "agents_used": final_state["agents_used"],
        "reasoning": final_state["reasoning"],
        "is_fallback": final_state["is_fallback"],
    }
    return validate_output(ChatResponse, result)
