# FinPilot 💰

**An AI financial copilot with built-in LLM evals and guardrails** — a multi-agent system that reasons about cash flow, runway, forecasts, and financial risk, and answers plain-English questions about the numbers, with its own reasoning checked and constrained at every step.

Built as a smaller, fully-understood version of a larger prior project — every agent, guardrail, and API call in this repo is real, tested, and traceable end-to-end.

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
- ✅ **Authenticated & multi-tenant** — JWT-based login with bcrypt-hashed passwords; every organization's data is fully isolated from every other's, enforced server-side, not by client cooperation

---

## Authentication & Authorization

FinPilot is multi-tenant: multiple organizations' data lives in the same
database, and the system is responsible for making sure one organization
can never see another's numbers — even if a client is modified or
malicious.

**Flow:**
```
User logs in (Streamlit)
    ↓
Node verifies credentials (bcrypt) against the users table
    ↓
Node creates a JWT containing { userId, organizationId, role }
    ↓
Streamlit stores the JWT for the session, sends it with every request:
    Authorization: Bearer <token>
    ↓
Node's `authenticate` middleware verifies the JWT signature + expiry
    ↓
Every route derives organization_id from req.user.organizationId —
NEVER from a query parameter, request body, or URL segment
    ↓
Database queries (and the forwarded call to the FastAPI agent service)
are scoped to that organization only
```

**The one rule that matters most:** the client never gets to say which
organization it wants to see. `GET /api/transactions?organization_id=20`
does not work — the `20` is simply never read. If you're authenticated as
organization 10, you see organization 10's data, full stop, regardless of
what any request parameter claims.

This is enforced at three layers, not just one:
1. **Route level** — every protected route pulls `org_id` from the verified
   JWT (`req.user.organizationId`), never from client input
2. **Query level** — single-record operations (`GET/PUT/DELETE /transactions/:id`)
   filter on `WHERE id = $1 AND org_id = $2` — a transaction ID belonging to
   another organization simply matches zero rows and returns 404, not a 403
   that would confirm the record exists
3. **Service boundary** — when Node forwards a request to the FastAPI agent
   service, it builds the params itself from `req.user.organizationId`,
   never by spreading the client's raw query string or body

**Getting your first login:** since there's no open sign-up (registration
requires an existing organization ID, and creating organizations is
admin-only), the very first organization and admin user are created via a
one-time CLI script, not an HTTP endpoint:
```bash
node node-api/scripts/create_org_and_admin.js "My Company" admin@example.com "a-strong-password"
```
After that, log in via the Streamlit app, or have that admin register
further users under the same organization via `POST /api/auth/register`.

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

Then bootstrap your first organization + admin user (also first run only):
```bash
node node-api/scripts/create_org_and_admin.js "My Company" admin@example.com "a-strong-password"
```

Visit:
- Dashboard → `http://localhost:8501` — log in with the email/password from the bootstrap step above
- API → `http://localhost:4000/health`
- Agent service docs → `http://localhost:8000/docs`

### Option B: Manual setup

See [`SETUP.md`](./SETUP.md) for step-by-step instructions to run each service (database, agent service, Node API, dashboard) without Docker.

### Configuration

Copy `.env.example` → `.env` in both `agent-service/` and `node-api/`, and fill in:
- `DATABASE_URL` — your PostgreSQL connection string
- `JWT_SECRET` — a strong random string (e.g. `openssl rand -hex 32`) used to sign login tokens; **required**, the app won't start without it
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
- **Registration is unauthenticated by design gap, not by intent** — `POST /api/auth/register` lets anyone create a user under any *existing* organization_id if they know or guess it (organization IDs are small sequential integers). It does not let them create a new org or access data without then logging in, but a production version should gate this behind an invitation token or admin-only creation, not open self-registration.
- **JWTs are not revocable** — there's no server-side session store, so a token remains valid until it expires (`JWT_EXPIRES_IN`, default 1h) even if the password is changed or the user should be logged out immediately. A production system would want a token blocklist or short-lived tokens + refresh tokens.
- **No rate limiting** on `/api/auth/login` — the current setup doesn't throttle repeated failed login attempts, so it's not resistant to password brute-forcing at scale.
- **No HTTPS enforcement at the app layer** — this relies entirely on the hosting platform (Render, etc.) terminating TLS; the app itself doesn't reject plaintext HTTP.
- **Single admin role only** — no per-permission granularity (e.g. "can view but not edit"); it's binary member/admin.

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

Built by [Eshu](https://linkedin.com/in/sanskar024) as a hands-on deep dive into multi-agent AI system design — every agent, guardrail, and integration in this repo was built and verified working end-to-end, not scaffolded and left unfinished.
