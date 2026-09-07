require("dotenv").config();
const express = require("express");
const cors = require("cors");

const authRouter = require("./routes/auth");
const organizationsRouter = require("./routes/organizations");
const transactionsRouter = require("./routes/transactions");
const cfoRouter = require("./routes/cfo");
const authenticate = require("./middleware/authenticate");

const app = express();
app.use(cors());
app.use(express.json());

app.get("/health", (req, res) => res.json({ status: "ok" }));

// Unauthenticated — this IS how you get a token in the first place.
app.use("/api/auth", authRouter);

// Everything below requires a valid JWT. organizationRouter has its own
// mix (GET /me requires auth; POST / requires auth + admin — see the
// file itself), so `authenticate` is applied per-route there, not here.
app.use("/api/organizations", organizationsRouter);
app.use("/api/transactions", authenticate, transactionsRouter);
app.use("/api/cfo", authenticate, cfoRouter);

const PORT = process.env.PORT || 4000;

if (require.main === module) {
  app.listen(PORT, () => console.log(`FinPilot Node API listening on port ${PORT}`));
}

module.exports = app;
