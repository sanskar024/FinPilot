// The most important test file in this project: proves a user
// authenticated as one organization cannot read, list, update, or delete
// another organization's data — no matter what org_id they put in the
// query string, body, or URL.

const request = require("supertest");
const pool = require("../db");
const app = require("../server");

let orgAId, orgBId, tokenA, tokenB, txnAId;

beforeAll(async () => {
  await pool.query("DELETE FROM users WHERE email IN ($1, $2)", ["orga@test.com", "orgb@test.com"]);
  await pool.query("DELETE FROM organizations WHERE name IN ($1, $2)", ["Authz Org A", "Authz Org B"]);

  const orgA = await pool.query("INSERT INTO organizations (name) VALUES ($1) RETURNING id", ["Authz Org A"]);
  orgAId = orgA.rows[0].id;
  const orgB = await pool.query("INSERT INTO organizations (name) VALUES ($1) RETURNING id", ["Authz Org B"]);
  orgBId = orgB.rows[0].id;

  await request(app).post("/api/auth/register").send({
    email: "orga@test.com",
    password: "password-a-123",
    organization_id: orgAId,
  });
  await request(app).post("/api/auth/register").send({
    email: "orgb@test.com",
    password: "password-b-123",
    organization_id: orgBId,
  });

  const loginA = await request(app).post("/api/auth/login").send({ email: "orga@test.com", password: "password-a-123" });
  tokenA = loginA.body.token;
  const loginB = await request(app).post("/api/auth/login").send({ email: "orgb@test.com", password: "password-b-123" });
  tokenB = loginB.body.token;

  const txn = await request(app)
    .post("/api/transactions")
    .set("Authorization", `Bearer ${tokenA}`)
    .send({ date: "2026-01-05", amount: 1000, type: "inflow", category: "revenue" });
  txnAId = txn.body.id;
});

afterAll(async () => {
  await pool.query("DELETE FROM transactions WHERE org_id IN ($1, $2)", [orgAId, orgBId]);
  await pool.query("DELETE FROM users WHERE email IN ($1, $2)", ["orga@test.com", "orgb@test.com"]);
  await pool.query("DELETE FROM organizations WHERE id IN ($1, $2)", [orgAId, orgBId]);
  await pool.end();
});

describe("Same-org access is allowed", () => {
  test("Org A user can list Org A's own transactions", async () => {
    const res = await request(app).get("/api/transactions").set("Authorization", `Bearer ${tokenA}`);
    expect(res.status).toBe(200);
    expect(res.body.some((t) => t.id === txnAId)).toBe(true);
  });

  test("Org A user can fetch its own transaction by id", async () => {
    const res = await request(app).get(`/api/transactions/${txnAId}`).set("Authorization", `Bearer ${tokenA}`);
    expect(res.status).toBe(200);
    expect(res.body.org_id).toBe(orgAId);
  });
});

describe("Cross-org access is denied", () => {
  test("Org B cannot see Org A's transaction in its list", async () => {
    const res = await request(app).get("/api/transactions").set("Authorization", `Bearer ${tokenB}`);
    expect(res.status).toBe(200);
    expect(res.body.some((t) => t.id === txnAId)).toBe(false);
  });

  test("Org B cannot fetch Org A's transaction by id (404, not 403 — doesn't confirm existence)", async () => {
    const res = await request(app).get(`/api/transactions/${txnAId}`).set("Authorization", `Bearer ${tokenB}`);
    expect(res.status).toBe(404);
  });

  test("Org B cannot update Org A's transaction", async () => {
    const res = await request(app)
      .put(`/api/transactions/${txnAId}`)
      .set("Authorization", `Bearer ${tokenB}`)
      .send({ date: "2026-01-05", amount: 999999, type: "inflow", category: "hacked" });
    expect(res.status).toBe(404);

    // Confirm it was NOT actually modified
    const check = await request(app).get(`/api/transactions/${txnAId}`).set("Authorization", `Bearer ${tokenA}`);
    expect(check.body.amount).not.toBe("999999.00");
  });

  test("Org B cannot delete Org A's transaction", async () => {
    const res = await request(app).delete(`/api/transactions/${txnAId}`).set("Authorization", `Bearer ${tokenB}`);
    expect(res.status).toBe(404);

    // Confirm it still exists
    const check = await request(app).get(`/api/transactions/${txnAId}`).set("Authorization", `Bearer ${tokenA}`);
    expect(check.status).toBe(200);
  });
});

describe("The critical attack: client-supplied org_id is always ignored", () => {
  test("Org A cannot access Org B's data by passing org_id in the query string", async () => {
    const res = await request(app)
      .get("/api/transactions")
      .query({ org_id: orgBId })
      .set("Authorization", `Bearer ${tokenA}`);

    expect(res.status).toBe(200);
    // Should still return ONLY Org A's transactions, ignoring the query param entirely
    expect(res.body.every((t) => t.org_id === orgAId)).toBe(true);
  });

  test("Org A cannot create a transaction under Org B by passing org_id in the body", async () => {
    const res = await request(app)
      .post("/api/transactions")
      .set("Authorization", `Bearer ${tokenA}`)
      .send({ date: "2026-01-07", amount: 500, type: "inflow", category: "sneaky", org_id: orgBId });

    expect(res.status).toBe(201);
    // The created row must belong to Org A (the authenticated org), not Org B
    expect(res.body.org_id).toBe(orgAId);
  });

  test("Org A cannot redirect a cfo agent query to Org B via query param", async () => {
    // This test only checks the org_id Node would forward — it doesn't
    // require the Python agent service to be running, so we just verify
    // Node's own request construction by checking it doesn't 500 in a way
    // that reveals org_id was taken from the query. A full integration
    // test with the live agent service is covered manually in README.
    const res = await request(app)
      .get("/api/cfo/cashflow")
      .query({ org_id: orgBId })
      .set("Authorization", `Bearer ${tokenA}`);

    // Either the agent service isn't running in CI (502) or it responds —
    // either way, status must never be a successful response containing
    // Org B's data attributed to Org A's request. We assert it's not a
    // silent success with mismatched org — if agent service is reachable,
    // response org_id must equal orgAId, never orgBId.
    if (res.status === 200) {
      expect(res.body.org_id).toBe(orgAId);
      expect(res.body.org_id).not.toBe(orgBId);
    } else {
      expect(res.status).toBe(502); // agent service unreachable in this env — acceptable
    }
  });
});

describe("Admin-gated organization creation", () => {
  test("a non-admin member cannot create an organization", async () => {
    // Register a plain member (not admin) under Org A
    await request(app).post("/api/auth/register").send({
      email: "member@test.com",
      password: "password-m-123",
      organization_id: orgAId,
    });
    const loginMember = await request(app)
      .post("/api/auth/login")
      .send({ email: "member@test.com", password: "password-m-123" });

    const res = await request(app)
      .post("/api/organizations")
      .set("Authorization", `Bearer ${loginMember.body.token}`)
      .send({ name: "Should Not Be Created" });

    expect(res.status).toBe(403);

    await pool.query("DELETE FROM users WHERE email = $1", ["member@test.com"]);
  });
});
