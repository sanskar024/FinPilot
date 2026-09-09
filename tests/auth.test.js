// These tests hit a real (test) database, since login/register are
// inherently DB-backed. Requires DATABASE_URL and JWT_SECRET set in the
// test environment (see package.json's "test" script / CI config).

const request = require("supertest");
const pool = require("../db");
const app = require("../server");

const TEST_ORG_NAME = "Auth Test Org";
const TEST_EMAIL = "authtest@example.com";
const TEST_PASSWORD = "correct-password-123";

let orgId;

beforeAll(async () => {
  // Clean slate for this org/user (idempotent re-runs)
  await pool.query("DELETE FROM users WHERE email = $1", [TEST_EMAIL]);
  await pool.query("DELETE FROM organizations WHERE name = $1", [TEST_ORG_NAME]);

  const orgResult = await pool.query(
    "INSERT INTO organizations (name) VALUES ($1) RETURNING id",
    [TEST_ORG_NAME]
  );
  orgId = orgResult.rows[0].id;

  await request(app).post("/api/auth/register").send({
    email: TEST_EMAIL,
    password: TEST_PASSWORD,
    organization_id: orgId,
  });
});

afterAll(async () => {
  await pool.query("DELETE FROM users WHERE email = $1", [TEST_EMAIL]);
  await pool.query("DELETE FROM organizations WHERE name = $1", [TEST_ORG_NAME]);
  await pool.end();
});

describe("POST /api/auth/login", () => {
  test("valid credentials return a JWT", async () => {
    const res = await request(app)
      .post("/api/auth/login")
      .send({ email: TEST_EMAIL, password: TEST_PASSWORD });

    expect(res.status).toBe(200);
    expect(res.body.token).toBeDefined();
    expect(res.body.user.organizationId).toBe(orgId);
  });

  test("wrong password returns 401", async () => {
    const res = await request(app)
      .post("/api/auth/login")
      .send({ email: TEST_EMAIL, password: "wrong-password" });

    expect(res.status).toBe(401);
  });

  test("unknown email returns 401 (same as wrong password — no user enumeration)", async () => {
    const res = await request(app)
      .post("/api/auth/login")
      .send({ email: "nobody-at-all@example.com", password: "whatever" });

    expect(res.status).toBe(401);
  });
});

describe("Protected routes without a valid token", () => {
  test("missing Authorization header returns 401", async () => {
    const res = await request(app).get("/api/transactions");
    expect(res.status).toBe(401);
  });

  test("malformed Authorization header (no Bearer prefix) returns 401", async () => {
    const res = await request(app).get("/api/transactions").set("Authorization", "just-a-token");
    expect(res.status).toBe(401);
  });

  test("garbage token returns 401", async () => {
    const res = await request(app)
      .get("/api/transactions")
      .set("Authorization", "Bearer this.is.not.a.valid.jwt");
    expect(res.status).toBe(401);
  });

  test("token signed with a different secret returns 401", async () => {
    const jwt = require("jsonwebtoken");
    const wrongSecretToken = jwt.sign({ userId: 1, organizationId: orgId, role: "member" }, "wrong-secret", {
      expiresIn: "1h",
    });
    const res = await request(app)
      .get("/api/transactions")
      .set("Authorization", `Bearer ${wrongSecretToken}`);
    expect(res.status).toBe(401);
  });

  test("expired token returns 401", async () => {
    const jwt = require("jsonwebtoken");
    const expiredToken = jwt.sign(
      { userId: 1, organizationId: orgId, role: "member" },
      process.env.JWT_SECRET,
      { expiresIn: "-1s" } // already expired
    );
    const res = await request(app)
      .get("/api/transactions")
      .set("Authorization", `Bearer ${expiredToken}`);
    expect(res.status).toBe(401);
  });
});
