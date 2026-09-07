// Proxies requests to the Python/FastAPI agent service.
//
// SECURITY-CRITICAL: every route here builds its own params object using
// ONLY req.user.organizationId — never `{ params: req.query }` or spreading
// req.body wholesale. Forwarding the client's raw query/body to FastAPI
// would let a client override org_id despite being authenticated as a
// different organization; FastAPI has no independent way to catch that,
// since it trusts whatever org_id Node sends it.

const express = require("express");
const axios = require("axios");

const router = express.Router();

const AGENT_SERVICE_URL = process.env.AGENT_SERVICE_URL || "http://localhost:8000";

function forwardError(res, err) {
  if (err.response) {
    return res.status(err.response.status).json(err.response.data);
  }
  console.error(err.message);
  return res.status(502).json({ error: "Agent service is unreachable" });
}

// GET /api/cfo/cashflow  (org comes from the JWT, never the client)
router.get("/cashflow", async (req, res) => {
  try {
    const response = await axios.get(`${AGENT_SERVICE_URL}/cashflow`, {
      params: { org_id: req.user.organizationId },
    });
    res.json(response.data);
  } catch (err) {
    forwardError(res, err);
  }
});

// GET /api/cfo/runway
router.get("/runway", async (req, res) => {
  try {
    const response = await axios.get(`${AGENT_SERVICE_URL}/runway`, {
      params: { org_id: req.user.organizationId },
    });
    res.json(response.data);
  } catch (err) {
    forwardError(res, err);
  }
});

// GET /api/cfo/forecast
router.get("/forecast", async (req, res) => {
  try {
    const response = await axios.get(`${AGENT_SERVICE_URL}/forecast`, {
      params: { org_id: req.user.organizationId },
    });
    res.json(response.data);
  } catch (err) {
    forwardError(res, err);
  }
});

// GET /api/cfo/risk
router.get("/risk", async (req, res) => {
  try {
    const response = await axios.get(`${AGENT_SERVICE_URL}/risk`, {
      params: { org_id: req.user.organizationId },
    });
    res.json(response.data);
  } catch (err) {
    forwardError(res, err);
  }
});

// POST /api/cfo/ask  { question }  — org_id is NOT accepted from the body.
router.post("/ask", async (req, res) => {
  const { question } = req.body;
  if (!question) {
    return res.status(400).json({ errors: ["question is required"] });
  }

  try {
    const response = await axios.post(`${AGENT_SERVICE_URL}/chat`, {
      org_id: req.user.organizationId,
      question,
    });
    res.json(response.data);
  } catch (err) {
    forwardError(res, err);
  }
});

module.exports = router;
