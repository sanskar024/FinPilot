const express = require("express");
const pool = require("../db");
const { validateOrganization } = require("../validation");
const authenticate = require("../middleware/authenticate");

const router = express.Router();

function requireAdmin(req, res, next) {
  if (req.user.role !== "admin") {
    return res.status(403).json({ error: "Only an admin can perform this action" });
  }
  return next();
}

// POST /api/organizations — admin-only. Creating an organization is a
// separate concern from accessing one's own organization's financial data;
// it's gated behind authentication + the admin role rather than left open,
// since an open endpoint here would let anyone spin up orgs at will.
// For bootstrapping the very first org+admin (before anyone can log in),
// use scripts/create_org_and_admin.js instead of this endpoint.
router.post("/", authenticate, requireAdmin, async (req, res) => {
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

// GET /api/organizations/me — returns only the authenticated user's own
// organization. Deliberately does NOT support listing all organizations
// or fetching one by an arbitrary id — that would leak org names/ids
// across tenants for no reason.
router.get("/me", authenticate, async (req, res) => {
  try {
    const result = await pool.query(
      "SELECT id, name, created_at FROM organizations WHERE id = $1",
      [req.user.organizationId]
    );
    if (result.rows.length === 0) {
      return res.status(404).json({ error: "Organization not found" });
    }
    res.json(result.rows[0]);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Failed to fetch organization" });
  }
});

module.exports = router;
