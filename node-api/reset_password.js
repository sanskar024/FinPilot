require("dotenv").config();
const pool = require("../db");
const { hashPassword } = require("../auth");

async function main() {
  const [, , email, password] = process.argv;
  if (!email || !password) {
    console.error('Usage: node scripts/reset_password.js email newpassword');
    process.exit(1);
  }
  const hash = await hashPassword(password);
  const r = await pool.query(
    "UPDATE users SET password_hash = $1 WHERE email = $2",
    [hash, email.toLowerCase().trim()]
  );
  console.log(r.rowCount === 1 ? "Password updated." : "No user found with that email.");
  await pool.end();
}
main().catch((e) => { console.error("Failed:", e.message); process.exit(1); });