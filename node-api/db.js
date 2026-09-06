// PostgreSQL connection pool. Reads DATABASE_URL from .env — never
// hardcode a connection string here (guardrail #7 from the README).

const { Pool } = require("pg");
require("dotenv").config();

if (!process.env.DATABASE_URL) {
  throw new Error("DATABASE_URL not set — copy .env.example to .env first.");
}

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
});

module.exports = pool;
