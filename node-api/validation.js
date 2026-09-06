// Pure validation functions — no DB, no network. Kept separate from the
// route handlers so they can be unit tested directly (see tests/).

const VALID_TYPES = ["inflow", "outflow"];

/**
 * Validates a transaction payload.
 * Returns { valid: true } or { valid: false, errors: [...] }.
 */
function validateTransaction(body) {
  const errors = [];

  if (body.org_id === undefined || body.org_id === null) {
    errors.push("org_id is required");
  } else if (!Number.isInteger(body.org_id) || body.org_id <= 0) {
    errors.push("org_id must be a positive integer");
  }

  if (!body.date) {
    errors.push("date is required");
  } else if (isNaN(Date.parse(body.date))) {
    errors.push("date must be a valid date");
  }

  if (body.amount === undefined || body.amount === null) {
    errors.push("amount is required");
  } else if (typeof body.amount !== "number" || body.amount <= 0) {
    errors.push("amount must be a positive number");
  }

  if (!body.type) {
    errors.push("type is required");
  } else if (!VALID_TYPES.includes(body.type)) {
    errors.push(`type must be one of: ${VALID_TYPES.join(", ")}`);
  }

  if (!body.category || typeof body.category !== "string" || body.category.trim() === "") {
    errors.push("category is required and must be a non-empty string");
  }

  // description is optional, but if present, cap its length — same spirit
  // as the input sanitizer on the Python side (guardrail #6/#7 area).
  if (body.description && typeof body.description === "string" && body.description.length > 500) {
    errors.push("description must be 500 characters or fewer");
  }

  return errors.length === 0 ? { valid: true, errors: [] } : { valid: false, errors };
}

/**
 * Validates an organization creation payload.
 */
function validateOrganization(body) {
  const errors = [];

  if (!body.name || typeof body.name !== "string" || body.name.trim() === "") {
    errors.push("name is required and must be a non-empty string");
  } else if (body.name.length > 200) {
    errors.push("name must be 200 characters or fewer");
  }

  return errors.length === 0 ? { valid: true, errors: [] } : { valid: false, errors };
}

module.exports = { validateTransaction, validateOrganization };
