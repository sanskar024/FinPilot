require("dotenv").config();
const express = require("express");
const cors = require("cors");

const organizationsRouter = require("./routes/organizations");
const transactionsRouter = require("./routes/transactions");
const cfoRouter = require("./routes/cfo");

const app = express();
app.use(cors());
app.use(express.json());

app.get("/health", (req, res) => res.json({ status: "ok" }));

app.use("/api/organizations", organizationsRouter);
app.use("/api/transactions", transactionsRouter);
app.use("/api/cfo", cfoRouter);

const PORT = process.env.PORT || 4000;

if (require.main === module) {
  app.listen(PORT, () => console.log(`FinPilot Node API listening on port ${PORT}`));
}

module.exports = app;
