# FinPilot

An AI financial copilot for small businesses — 5 LangGraph agents (Cashflow,
Runway, Forecast, Risk/Anomaly, and a CFO Chat orchestrator) sitting behind a
Node/Express API, backed by PostgreSQL, with a Streamlit dashboard on top.

See the full design doc for architecture, agent responsibilities, and the
reasoning behind every stack choice. This file is just "how do I run it."

Everything in this repo has been run and tested against real seeded data
during development — not just written and assumed to work.

---

## Option A: Run with Docker (recommended)

Requires Docker and Docker Compose installed.

```bash
# 1. (Optional) set an Anthropic API key for LLM-powered chat answers.
#    Without it, the CFO Chat Agent still works — it falls back to a
#    template-based summary of the agents' own explanations.
export ANTHROPIC_API_KEY=sk-ant-...

# 2. Build and start everything
docker-compose up --build

# 3. Seed the database (first run only, in a new terminal)
docker-compose exec postgres psql -U finpilot_user -d finpilot -c "SELECT 1"  # sanity check it's up
python data/generate_seed_data.py   # writes data/seed_transactions.csv
DATABASE_URL=postgresql://finpilot_user:finpilot_pass@localhost:5432/finpilot python database/load_seed.py
```

Then visit:
- Dashboard: http://localhost:8501
- Node API: http://localhost:4000/health
- Agent service docs: http://localhost:8000/docs

---

## Option B: Run manually (no Docker)

Requires PostgreSQL, Python 3.12+, and Node 22+ installed locally.

### 1. Database

```bash
# Create the database and user (adjust to your local Postgres setup)
psql -c "CREATE USER finpilot_user WITH PASSWORD 'finpilot_pass';"
psql -c "CREATE DATABASE finpilot OWNER finpilot_user;"

# Apply the schema
psql -h localhost -U finpilot_user -d finpilot -f database/schema.sql
```

### 2. Seed data

```bash
cd data
python generate_seed_data.py       # writes seed_transactions.csv

cd ../database
cp .env.example .env               # fill in DATABASE_URL
pip install psycopg2-binary python-dotenv
python load_seed.py
```

### 3. Agent service (Python/FastAPI)

```bash
cd agent-service
cp .env.example .env               # fill in DATABASE_URL
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

Run the tests and evals:
```bash
pytest tests/ -v
python -m evals.run_evals
```

### 4. Node API

```bash
cd node-api
cp .env.example .env               # fill in DATABASE_URL and AGENT_SERVICE_URL
npm install
npm start
```

Run the tests:
```bash
npm test
```

### 5. Dashboard (Streamlit)

```bash
cd dashboard
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Visit http://localhost:8501

---

## Project Structure

```
finpilot/
├── node-api/          # Express API — transaction/org CRUD + proxy to agent-service
├── agent-service/      # FastAPI + LangGraph — the 5 agents, guardrails, evals, tests
├── dashboard/          # Streamlit — charts + chat UI
├── database/           # schema.sql + load_seed.py
├── data/                # generate_seed_data.py + generated CSV
└── docker-compose.yml
```

See each folder for its own logic; the design doc covers why it's structured
this way.

## Known Limitations (being upfront, since this matters for how you present it)

- The Forecast Agent uses a simple linear trend, not a "real" time-series
  model (ARIMA/Prophet/etc.) — that's a deliberate choice for explainability,
  not an oversight, but worth saying out loud if asked.
- The CFO Chat Agent's LLM synthesis step requires `ANTHROPIC_API_KEY` to be
  set; without it, answers are template-based summaries of the agents' raw
  output rather than natural-language synthesis.
- Seed data is synthetic and historical (dated March–August 2026) — agents
  anchor on the latest transaction date in the data, not the real current
  date, since this isn't a live feed.
- No authentication/multi-tenancy — `org_id` is passed directly with no
  access control, which is fine for a single-user demo but would need
  addressing before any real multi-user use.
"# FinPilot" 
