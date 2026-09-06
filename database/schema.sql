-- FinPilot database schema
-- Two tables on purpose: enough to compute every agent's metrics,
-- small enough to hold in your head.

CREATE TABLE IF NOT EXISTS organizations (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS transactions (
    id           SERIAL PRIMARY KEY,
    org_id       INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    date         DATE NOT NULL,
    amount       NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
    type         TEXT NOT NULL CHECK (type IN ('inflow', 'outflow')),
    category     TEXT NOT NULL,
    description  TEXT
);

-- Index for the most common query pattern: "give me all transactions
-- for org X between two dates" (every agent does this).
CREATE INDEX IF NOT EXISTS idx_transactions_org_date
    ON transactions (org_id, date);
