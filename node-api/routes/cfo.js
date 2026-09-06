// Proxies requests to the Python/FastAPI agent service. This is the exact
// piece (agent.service.js) that was an empty stub file in the original
// FINTRO codebase — here it's a real, working connection.

const express = require("express");
const axios = require("axios");

const router = express.Router();

const AGENT_SERVICE_URL = process.env.AGENT_SERVICE_URL || "http://localhost:8000";

function forwardError(res, err) {
  if (err.response) {
    // The agent service responded with an error status — forward it as-is
    // rather than masking it as a generic 500.
    return res.status(err.response.status).json(err.response.data);
  }
  console.error(err.message);
  return res.status(502).json({ error: "Agent service is unreachable" });
}

// GET /api/cfo/cashflow?org_id=1
router.get("/cashflow", async (req, res) => {
  try {
    const response = await axios.get(`${AGENT_SERVICE_URL}/cashflow`, { params: req.query });
    res.json(response.data);
  } catch (err) {
    forwardError(res, err);
  }
});

// GET /api/cfo/runway?org_id=1
router.get("/runway", async (req, res) => {
  try {
    const response = await axios.get(`${AGENT_SERVICE_URL}/runway`, { params: req.query });
    res.json(response.data);
  } catch (err) {
    forwardError(res, err);
  }
});

// GET /api/cfo/forecast?org_id=1
router.get("/forecast", async (req, res) => {
  try {
    const response = await axios.get(`${AGENT_SERVICE_URL}/forecast`, { params: req.query });
    res.json(response.data);
  } catch (err) {
    forwardError(res, err);
  }
});

// GET /api/cfo/risk?org_id=1
router.get("/risk", async (req, res) => {
  try {
    const response = await axios.get(`${AGENT_SERVICE_URL}/risk`, { params: req.query });
    res.json(response.data);
  } catch (err) {
    forwardError(res, err);
  }
});

// POST /api/cfo/ask  { org_id, question }
router.post("/ask", async (req, res) => {
  const { org_id, question } = req.body;
  if (!org_id || !question) {
    return res.status(400).json({ errors: ["org_id and question are both required"] });
  }

  try {
    const response = await axios.post(`${AGENT_SERVICE_URL}/chat`, { org_id, question });
    res.json(response.data);
  } catch (err) {
    forwardError(res, err);
  }
});

module.exports = router;
