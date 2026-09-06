const { validateTransaction, validateOrganization } = require("../validation");

describe("validateTransaction", () => {
  test("accepts a valid transaction", () => {
    const result = validateTransaction({
      org_id: 1,
      date: "2026-03-01",
      amount: 100.5,
      type: "outflow",
      category: "rent",
    });
    expect(result.valid).toBe(true);
    expect(result.errors).toEqual([]);
  });

  test("rejects a negative amount", () => {
    const result = validateTransaction({
      org_id: 1,
      date: "2026-03-01",
      amount: -50,
      type: "outflow",
      category: "rent",
    });
    expect(result.valid).toBe(false);
    expect(result.errors).toContain("amount must be a positive number");
  });

  test("rejects a zero amount", () => {
    const result = validateTransaction({
      org_id: 1,
      date: "2026-03-01",
      amount: 0,
      type: "outflow",
      category: "rent",
    });
    expect(result.valid).toBe(false);
  });

  test("rejects an invalid type", () => {
    const result = validateTransaction({
      org_id: 1,
      date: "2026-03-01",
      amount: 100,
      type: "sideways",
      category: "rent",
    });
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes("type must be one of"))).toBe(true);
  });

  test("rejects a missing category", () => {
    const result = validateTransaction({
      org_id: 1,
      date: "2026-03-01",
      amount: 100,
      type: "outflow",
    });
    expect(result.valid).toBe(false);
  });

  test("rejects an invalid date", () => {
    const result = validateTransaction({
      org_id: 1,
      date: "not-a-date",
      amount: 100,
      type: "outflow",
      category: "rent",
    });
    expect(result.valid).toBe(false);
  });

  test("rejects a non-integer org_id", () => {
    const result = validateTransaction({
      org_id: 1.5,
      date: "2026-03-01",
      amount: 100,
      type: "outflow",
      category: "rent",
    });
    expect(result.valid).toBe(false);
  });

  test("rejects an overly long description", () => {
    const result = validateTransaction({
      org_id: 1,
      date: "2026-03-01",
      amount: 100,
      type: "outflow",
      category: "rent",
      description: "a".repeat(501),
    });
    expect(result.valid).toBe(false);
  });
});

describe("validateOrganization", () => {
  test("accepts a valid organization", () => {
    const result = validateOrganization({ name: "Acme Studio" });
    expect(result.valid).toBe(true);
  });

  test("rejects an empty name", () => {
    const result = validateOrganization({ name: "" });
    expect(result.valid).toBe(false);
  });

  test("rejects a missing name", () => {
    const result = validateOrganization({});
    expect(result.valid).toBe(false);
  });
});
