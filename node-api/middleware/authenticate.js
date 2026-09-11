// Authentication middleware. Every protected route depends on this having
// run first and populated req.user — routes must NEVER read organization_id
// from req.query or req.body; only from req.user.organizationId, which is
// only ever set here, only after a signature has been verified.

const { verifyToken } = require("../auth");

function authenticate(req, res, next) {
  const authHeader = req.headers.authorization;

  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    return res.status(401).json({ error: "Missing or malformed Authorization header" });
  }

  const token = authHeader.slice("Bearer ".length).trim();
  if (!token) {
    return res.status(401).json({ error: "Missing token" });
  }

  try {
    const decoded = verifyToken(token);
    // decoded contains exactly what signToken put in: userId, organizationId, role
    req.user = decoded;
    return next();
  } catch (err) {
    // Covers: invalid signature, malformed token, AND expired token
    // (jsonwebtoken throws TokenExpiredError, a subclass caught here too).
    return res.status(401).json({ error: "Invalid or expired token" });
  }
}

module.exports = authenticate;
