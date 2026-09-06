const express = require("express");
const pool = require("../db");
const { validateOrganization } = require("../validation");

const router = express.Router();

// POST /api/organizations
router.post("/", async (req, res) => {
  const { valid, errors } = validateOrganization(req.body);
  if (!valid) {
    return res.status(400).json({ errors });
  }

  try {
    const result = await pool.query(
      "INSERT INTO organizations (name) VALUES ($1) RETURNING id, name, created_at",
      [req.body.name.trim()]
    );
    res.status(201).json(result.rows[0]);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Failed to create organization" });
  }
});

// GET /api/organizations
router.get("/", async (req, res) => {
  try {
    const result = await pool.query("SELECT id, name, created_at FROM organizations ORDER BY id");
    res.json(result.rows);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Failed to fetch organizations" });
  }
});

module.exports = router;
