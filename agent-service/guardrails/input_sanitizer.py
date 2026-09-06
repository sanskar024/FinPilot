"""
Input sanitizer guardrail — checks free-text input (chat questions,
transaction descriptions) for prompt-injection patterns before it's ever
concatenated into an LLM prompt.

This isn't foolproof (no keyword list ever is), but it catches the
obvious, common injection phrasings and enforces a sane length limit —
which is the realistic bar for a project like this, not "unbreakable."
"""

MAX_INPUT_LENGTH = 500

INJECTION_PATTERNS = [
    "ignore previous instructions",
    "ignore all previous instructions",
    "disregard previous instructions",
    "disregard the above",
    "you are now",
    "system prompt",
    "reveal your instructions",
    "act as if",
    "new instructions:",
]


def sanitize_input(text: str) -> dict:
    """
    Returns {"safe": bool, "reason": str | None, "cleaned": str}.
    `cleaned` is the trimmed input if safe, otherwise the original text
    (there's nothing safe to "clean" — the caller should reject it, not
    pass a modified version through).
    """
    if text is None:
        return {"safe": False, "reason": "Input was empty.", "cleaned": ""}

    trimmed = text.strip()

    if len(trimmed) == 0:
        return {"safe": False, "reason": "Input was empty.", "cleaned": ""}

    if len(trimmed) > MAX_INPUT_LENGTH:
        return {
            "safe": False,
            "reason": f"Input exceeds the {MAX_INPUT_LENGTH} character limit.",
            "cleaned": trimmed,
        }

    lowered = trimmed.lower()
    for pattern in INJECTION_PATTERNS:
        if pattern in lowered:
            return {
                "safe": False,
                "reason": "Input contains a disallowed instruction-override pattern.",
                "cleaned": trimmed,
            }

    return {"safe": True, "reason": None, "cleaned": trimmed}
