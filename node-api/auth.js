// Auth primitives: password hashing (bcrypt) and JWT sign/verify.
// Kept separate from route handlers so they're unit-testable without an
// HTTP server or a database (same pattern as validation.js).

const bcrypt = require("bcrypt");
const jwt = require("jsonwebtoken");

const SALT_ROUNDS = 10;

function getJwtSecret() {
  const secret = process.env.JWT_SECRET;
  if (!secret) {
    throw new Error("JWT_SECRET not set — copy .env.example to .env first.");
  }
  return secret;
}

async function hashPassword(plainTextPassword) {
  return bcrypt.hash(plainTextPassword, SALT_ROUNDS);
}

async function verifyPassword(plainTextPassword, passwordHash) {
  return bcrypt.compare(plainTextPassword, passwordHash);
}

/**
 * Signs a JWT containing ONLY the minimum identity needed for authorization:
 * userId + organizationId. Never put passwords, financial data, or anything
 * sensitive in the token — it's not encrypted, just signed, so anyone can
 * decode (not forge) its contents.
 */
function signToken({ userId, organizationId, role }) {
  const expiresIn = process.env.JWT_EXPIRES_IN || "1h";
  return jwt.sign({ userId, organizationId, role }, getJwtSecret(), { expiresIn });
}

/**
 * Verifies a JWT. Throws on invalid signature, malformed token, or
 * expiration — callers (the auth middleware) are expected to catch this
 * and respond 401, not let it propagate as a 500.
 */
function verifyToken(token) {
  return jwt.verify(token, getJwtSecret());
}

module.exports = { hashPassword, verifyPassword, signToken, verifyToken };
