# FinPilot 💰

**An AI financial  multi-agent system  copilot with built-in LLM evals and guardrails** — that reasons about cash flow, runway, forecasts, and financial risk, and answers plain-English questions about the numbers, with its own reasoning checked and constrained at every step.

---

## What it does

- 📊 **Cash flow analysis** — inflows, outflows, burn rate, spend by category
- 🛫 **Runway projection** — months of cash remaining, based on real transaction history (not a hardcoded balance)
- 📈 **Forecasting** — a transparent linear-trend model for future weeks, with **backtesting** against real held-out data so accuracy is measured, not assumed
- 🚨 **Anomaly detection** — flags unusual spending and missing/delayed revenue using explainable statistics (z-scores), not a black-box model
- 💬 **Natural-language chat** — ask questions like *"can we afford to hire someone next month?"* and get an answer grounded in the actual data, with the reasoning shown, not hidden

---

## Architecture

```
Streamlit  →  Node.js/Express  →  FastAPI + LangGraph (5 agents)  →  PostgreSQL
 (chat +        (API layer +          (Cashflow, Runway,
 dashboard)      proxy)                Forecast, Risk,
                                        CFO Chat orchestrator)
```

- **Streamlit** never talks to the database directly — everything goes through Node, so there's one clear entry point into the system.
- **Node.js** owns writes (adding transactions); **FastAPI** owns reads-for-reasoning (every agent call).
- The **CFO Chat Agent** is a real [LangGraph](https://github.com/langchain-ai/langgraph) state graph: guardrail check → route → call agents → synthesize → validate. Guardrails run *before* any agent or LLM call — a blocked question never touches the database.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit |
| API layer | Node.js + Express |
| Agent orchestration | Python + FastAPI + LangGraph |
| Database | PostgreSQL + SQLAlchemy |
| LLM (optional) | Pluggable — works with Anthropic or Gemini; falls back to a template-based answer if no key is set |

---

## Engineering practices this project demonstrates

- ✅ **Tested** — 20 pytest unit tests + 11 Jest tests, all passing
- ✅ **Evaluated** — an 18-question golden eval set scoring the orchestrator's routing and answer accuracy (18/18 passing)
- ✅ **Guardrailed** — scope checking, prompt-injection input sanitization, and Pydantic output-schema validation, all wired in *before* the LLM is ever called
- ✅ **Backtested forecasting** — predictions are checked against real held-out data, with mean absolute error reported
- ✅ **No hardcoded financial data** — every number is computed live from the transaction history
- ✅ **No secrets in the repo** — `.env.example` templates only; real credentials are git-ignored
- ✅ **Containerized** — one `docker-compose up` runs the full stack

---

## Getting Started

### Option A: Docker (recommended)

```bash
git clone <this-repo>
cd finpilot
docker-compose up --build
```

Then seed the database (first run only):
```bash
python data/generate_seed_data.py
DATABASE_URL=<your-connection-string> python database/load_seed.py
```

Visit:
- Dashboard → `http://localhost:8501`
- API → `http://localhost:4000/health`
- Agent service docs → `http://localhost:8000/docs`

### Option B: Manual setup

See [`SETUP.md`](./SETUP.md) for step-by-step instructions to run each service (database, agent service, Node API, dashboard) without Docker.

### Configuration

Copy `.env.example` → `.env` in both `agent-service/` and `node-api/`, and fill in:
- `DATABASE_URL` — your PostgreSQL connection string
- `ANTHROPIC_API_KEY` or `GEMINI_API_KEY` *(optional)* — enables LLM-powered chat synthesis; without it, the CFO Chat Agent still works, using a template-based summary of the agents' own findings

---

## Running the Tests & Evals

```bash
# Python agent tests
cd agent-service
pytest tests/ -v

# Eval suite (checks the orchestrator's routing + answer accuracy)
python -m evals.run_evals

# Node API tests
cd node-api
npm test
```

---

## Known Limitations

- The forecast uses a simple linear trend, not ARIMA/Prophet — a deliberate choice for explainability
- Seed data is synthetic and historical; agents anchor on the latest transaction date in the data, not the live system clock
- No authentication/multi-tenancy — this is a single-org demo, not production-ready for multiple users

---

## Project Structure

```
finpilot/
├── node-api/          # Express API — transaction/org CRUD + proxy to agent-service
├── agent-service/      # FastAPI + LangGraph — the 5 agents, guardrails, evals, tests
├── dashboard/          # Streamlit — charts + chat UI
├── database/            # schema.sql + seed loader
├── data/                 # synthetic data generator
└── docker-compose.yml
```

---

## Author

Built by [Sankar gupta](https://linkedin.com/in/sanskar024) as a hands-on deep dive into multi-agent AI system design — every agent, guardrail, and integration in this repo was built and verified working end-to-end, not scaffolded and left unfinished.
