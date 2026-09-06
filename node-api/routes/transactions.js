// Transactions routes. Every route here is protected by `authenticate`
// (mounted in server.js), and organization_id is ALWAYS taken from
// req.user.organizationId — never from req.query, req.body, or req.params.
// A client cannot access another organization's data by changing a query
// parameter, because the parameter is never consulted for that purpose.

const express = require("express");
const pool = require("../db");
const { validateTransaction } = require("../validation");

const router = express.Router();

// POST /api/transactions
// Note: org_id is deliberately NOT read from req.body even if the client
// sends one — it's always req.user.organizationId. If a client sends a
// mismatched org_id in the body, it's silently ignored, not honored.
router.post("/", async (req, res) => {
  const payloadForValidation = { ...req.body, org_id: req.user.organizationId };
  const { valid, errors } = validateTransaction(payloadForValidation);
  if (!valid) {
    return res.status(400).json({ errors });
  }

  const { date, amount, type, category, description } = req.body;
  const orgId = req.user.organizationId;

  try {
    const result = await pool.query(
      `INSERT INTO transactions (org_id, date, amount, type, category, description)
       VALUES ($1, $2, $3, $4, $5, $6)
       RETURNING id, org_id, date, amount, type, category, description`,
      [orgId, date, amount, type, category, description || null]
    );
    res.status(201).json(result.rows[0]);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Failed to create transaction" });
  }
});

// GET /api/transactions — lists only the authenticated user's own
// organization's transactions. No org_id query parameter is accepted or
// consulted at all.
router.get("/", async (req, res) => {
  const orgId = req.user.organizationId;

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

// GET /api/transactions/:id — ownership-checked. The WHERE clause filters
// on BOTH id AND org_id, so a transaction id belonging to another
// organization simply doesn't match any row and returns 404 — not a 403
// that would confirm the id exists but belongs to someone else.
router.get("/:id", async (req, res) => {
  const id = parseInt(req.params.id, 10);
  const orgId = req.user.organizationId;
  if (!id) {
    return res.status(400).json({ errors: ["id must be an integer"] });
  }

  try {
    const result = await pool.query(
      "SELECT id, org_id, date, amount, type, category, description FROM transactions WHERE id = $1 AND org_id = $2",
      [id, orgId]
    );
    if (result.rows.length === 0) {
      return res.status(404).json({ error: "Transaction not found" });
    }
    res.json(result.rows[0]);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Failed to fetch transaction" });
  }
});

// PUT /api/transactions/:id — ownership-checked update. Same WHERE-clause
// pattern: the UPDATE itself is scoped to (id AND org_id), so it's
// impossible to update a row you don't own even if you guess its id.
router.put("/:id", async (req, res) => {
  const id = parseInt(req.params.id, 10);
  const orgId = req.user.organizationId;
  if (!id) {
    return res.status(400).json({ errors: ["id must be an integer"] });
  }

  const payloadForValidation = { ...req.body, org_id: orgId };
  const { valid, errors } = validateTransaction(payloadForValidation);
  if (!valid) {
    return res.status(400).json({ errors });
  }

  const { date, amount, type, category, description } = req.body;

  try {
    const result = await pool.query(
      `UPDATE transactions
       SET date = $1, amount = $2, type = $3, category = $4, description = $5
       WHERE id = $6 AND org_id = $7
       RETURNING id, org_id, date, amount, type, category, description`,
      [date, amount, type, category, description || null, id, orgId]
    );
    if (result.rows.length === 0) {
      return res.status(404).json({ error: "Transaction not found" });
    }
    res.json(result.rows[0]);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Failed to update transaction" });
  }
});

// DELETE /api/transactions/:id — same ownership-checked pattern.
router.delete("/:id", async (req, res) => {
  const id = parseInt(req.params.id, 10);
  const orgId = req.user.organizationId;
  if (!id) {
    return res.status(400).json({ errors: ["id must be an integer"] });
  }

  try {
    const result = await pool.query(
      "DELETE FROM transactions WHERE id = $1 AND org_id = $2 RETURNING id",
      [id, orgId]
    );
    if (result.rows.length === 0) {
      return res.status(404).json({ error: "Transaction not found" });
    }
    res.status(204).send();
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Failed to delete transaction" });
  }
});

module.exports = router;
