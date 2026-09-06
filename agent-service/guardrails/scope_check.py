"""
Scope guardrail — rejects questions that aren't about the business's
finances, before any agent or LLM call is made.

Deliberately simple (keyword-based) rather than another LLM call: a
guardrail that itself depends on an LLM is a guardrail that can be
prompt-injected or that fails silently if that LLM call errors. A cheap,
fast, dependency-free check is more trustworthy for the "front door."
"""

FINANCE_KEYWORDS = {
    "cash", "cashflow", "cash flow", "burn", "runway", "revenue", "income",
    "expense", "expenses", "spend", "spending", "spent", "outflow", "inflow",
    "forecast", "projection", "project", "risk", "anomaly", "anomalies",
    "unusual", "suspicious", "transaction", "transactions", "payroll",
    "rent", "invoice", "payment", "budget", "profit", "loss", "balance",
    "afford", "hire", "hiring", "cost", "costs", "financial", "finance",
    "money", "margin", "growth", "trend", "business", "company",
    "performance", "doing",
}


def is_in_scope(question: str) -> bool:
    """Returns True if the question contains at least one finance-related keyword."""
    lowered = question.lower()
    return any(keyword in lowered for keyword in FINANCE_KEYWORDS)


def scope_check(question: str) -> dict:
    """
    Returns a structured result rather than raising, so the caller can
    decide how to respond (this also makes the check itself unit-testable
    without needing to catch exceptions).
    """
    if is_in_scope(question):
        return {"allowed": True, "reason": None}
    return {
        "allowed": False,
        "reason": (
            "This assistant only answers questions about your business's finances "
            "(cash flow, runway, forecasts, spending, risk). Try asking about one of those."
        ),
    }
