const express = require("express");
const pool = require("../db");
const { validateTransaction } = require("../validation");

const router = express.Router();

// POST /api/transactions
router.post("/", async (req, res) => {
  const { valid, errors } = validateTransaction(req.body);
  if (!valid) {
    return res.status(400).json({ errors });
  }

  const { org_id, date, amount, type, category, description } = req.body;

  try {
    const result = await pool.query(
      `INSERT INTO transactions (org_id, date, amount, type, category, description)
       VALUES ($1, $2, $3, $4, $5, $6)
       RETURNING id, org_id, date, amount, type, category, description`,
      [org_id, date, amount, type, category, description || null]
    );
    res.status(201).json(result.rows[0]);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Failed to create transaction" });
  }
});

// GET /api/transactions?org_id=1
router.get("/", async (req, res) => {
  const orgId = parseInt(req.query.org_id, 10);
  if (!orgId) {
    return res.status(400).json({ errors: ["org_id query parameter is required and must be an integer"] });
  }

  try {
    const result = await pool.query(
      "SELECT id, org_id, date, amount, type, category, description FROM transactions WHERE org_id = $1 ORDER BY date",
      [orgId]
    );
    res.json(result.rows);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Failed to fetch transactions" });
  }
});

module.exports = router;
