"""
Loads data/seed_transactions.csv into the PostgreSQL database.

Creates one organization ("Acme Studio") and attaches every row from the
CSV to it. Safe to re-run: it wipes existing transactions for that org
first, so you don't end up with duplicates if you run it twice.

Requires DATABASE_URL to be set (loaded from .env via python-dotenv).

Run with: python load_seed.py
"""

import csv
import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "seed_transactions.csv")
ORG_NAME = "Acme Studio"

if not DATABASE_URL:
    raise SystemExit("DATABASE_URL not set — copy .env.example to .env first.")

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# Get-or-create the organization
cur.execute("SELECT id FROM organizations WHERE name = %s", (ORG_NAME,))
row = cur.fetchone()
if row:
    org_id = row[0]
else:
    cur.execute(
        "INSERT INTO organizations (name) VALUES (%s) RETURNING id",
        (ORG_NAME,),
    )
    org_id = cur.fetchone()[0]

# Wipe existing transactions for this org so re-running doesn't duplicate
cur.execute("DELETE FROM transactions WHERE org_id = %s", (org_id,))

with open(CSV_PATH, newline="") as f:
    reader = csv.DictReader(f)
    count = 0
    for row in reader:
        cur.execute(
            """
            INSERT INTO transactions (org_id, date, amount, type, category, description)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (org_id, row["date"], row["amount"], row["type"], row["category"], row["description"]),
        )
        count += 1

conn.commit()
cur.close()
conn.close()

print(f"Loaded {count} transactions for org '{ORG_NAME}' (id={org_id})")
