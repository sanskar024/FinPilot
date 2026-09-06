"""
Eval runner — runs the CFO Chat Agent against evals/golden_set.json and
scores it on three things per question:

  1. routing_correct  — did it call the expected agent(s)?
  2. blocked_correct  — did a guardrail fire exactly when it should have?
  3. content_correct  — does the answer contain the expected substring(s)?

This is what CI would run alongside the pytest suite — a change that
breaks the orchestrator's reasoning fails this script, not just "seems
fine" on manual spot-checks.

Run with: python -m evals.run_evals
(from the agent-service/ directory, with DATABASE_URL set)
"""

import json
import os

from agents.cfo_chat_agent import run_cfo_chat_agent
from db.session import SessionLocal

GOLDEN_SET_PATH = os.path.join(os.path.dirname(__file__), "golden_set.json")


def evaluate_one(session, case: dict) -> dict:
    result = run_cfo_chat_agent(session, org_id=1, question=case["question"])

    routing_correct = sorted(result["agents_used"]) == sorted(case["expected_agents"])
    blocked_correct = result["is_fallback"] and not result["agents_used"] if case["expect_blocked"] else True
    # For non-blocked cases, blocked_correct just means it wasn't wrongly blocked
    if not case["expect_blocked"]:
        blocked_correct = bool(result["agents_used"]) or not case["expected_agents"]

    answer_lower = result["answer"].lower()
    content_correct = all(sub.lower() in answer_lower for sub in case["must_contain"])

    passed = routing_correct and blocked_correct and content_correct

    return {
        "id": case["id"],
        "question": case["question"],
        "passed": passed,
        "routing_correct": routing_correct,
        "blocked_correct": blocked_correct,
        "content_correct": content_correct,
        "expected_agents": case["expected_agents"],
        "actual_agents": result["agents_used"],
        "answer_preview": result["answer"][:150],
    }


def run_evals():
    with open(GOLDEN_SET_PATH) as f:
        golden_set = json.load(f)

    session = SessionLocal()
    results = [evaluate_one(session, case) for case in golden_set]
    session.close()

    passed = sum(1 for r in results if r["passed"])
    total = len(results)

    print(f"\n{'='*60}")
    print(f"EVAL RESULTS: {passed}/{total} passed")
    print(f"{'='*60}\n")

    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"[{status}] {r['id']}: \"{r['question'][:50]}\"")
        if not r["passed"]:
            print(f"       routing_correct={r['routing_correct']} (expected={r['expected_agents']}, got={r['actual_agents']})")
            print(f"       blocked_correct={r['blocked_correct']}  content_correct={r['content_correct']}")
            print(f"       answer preview: {r['answer_preview']}")

    return passed, total


if __name__ == "__main__":
    passed, total = run_evals()
    exit(0 if passed == total else 1)
