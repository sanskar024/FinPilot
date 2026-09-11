// Authentication routes: /login and /register.
//
// /register is intentionally simple (setup/demo purposes) — a real product
// would gate signup behind invitations, email verification, or an admin
// console. It's included here so the auth flow is actually usable end to
// end, but it's documented as a known limitation in the README.

const express = require("express");
const pool = require("../db");
const { hashPassword, verifyPassword, signToken } = require("../auth");

const router = express.Router();

function isValidEmail(email) {
  return typeof email === "string" && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

// POST /api/auth/register  { email, password, organization_id }
// Creates a user under an EXISTING organization. Does not create orgs —
// that's a separate, admin-only action (see routes/organizations.js).
router.post("/register", async (req, res) => {
  const { email, password, organization_id } = req.body;
  const errors = [];

  if (!isValidEmail(email)) errors.push("A valid email is required");
  if (!password || typeof password !== "string" || password.length < 8) {
    errors.push("Password must be at least 8 characters");
  }
  if (!Number.isInteger(organization_id) || organization_id <= 0) {
    errors.push("organization_id must be a positive integer");
  }
  if (errors.length > 0) {
    return res.status(400).json({ errors });
  }

  try {
    const orgCheck = await pool.query("SELECT id FROM organizations WHERE id = $1", [organization_id]);
    if (orgCheck.rows.length === 0) {
      return res.status(400).json({ errors: ["organization_id does not refer to an existing organization"] });
    }

    const passwordHash = await hashPassword(password);
    const result = await pool.query(
      `INSERT INTO users (email, password_hash, organization_id)
       VALUES ($1, $2, $3)
       RETURNING id, email, organization_id, role, created_at`,
      [email.toLowerCase().trim(), passwordHash, organization_id]
    );

    const user = result.rows[0];
    const token = signToken({ userId: user.id, organizationId: user.organization_id, role: user.role });

    res.status(201).json({ token, user: { id: user.id, email: user.email, organizationId: user.organization_id, role: user.role } });
  } catch (err) {
    if (err.code === "23505") {
      // unique_violation on email
      return res.status(400).json({ errors: ["An account with this email already exists"] });
    }
    console.error(err);
    res.status(500).json({ error: "Failed to register user" });
  }
});

// POST /api/auth/login  { email, password }
router.post("/login", async (req, res) => {
  const { email, password } = req.body;

  if (!isValidEmail(email) || !password) {
    return res.status(401).json({ error: "Invalid email or password" });
  }

  try {
    const result = await pool.query(
      "SELECT id, email, password_hash, organization_id, role FROM users WHERE email = $1",
      [email.toLowerCase().trim()]
    );

    if (result.rows.length === 0) {
      // Deliberately the SAME error/status as a wrong password — never
      // reveal whether an email exists in the system.
      return res.status(401).json({ error: "Invalid email or password" });
    }

    const user = result.rows[0];
    const passwordOk = await verifyPassword(password, user.password_hash);
    if (!passwordOk) {
      return res.status(401).json({ error: "Invalid email or password" });
    }

    const token = signToken({ userId: user.id, organizationId: user.organization_id, role: user.role });
    res.json({ token, user: { id: user.id, email: user.email, organizationId: user.organization_id, role: user.role } });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Login failed" });
  }
});

module.exports = router;
