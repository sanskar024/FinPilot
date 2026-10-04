require("dotenv").config();
const pool = require("../db");
const { verifyPassword } = require("../auth");

(async () => {
  const [, , email, password] = process.argv;
  const r = await pool.query("SELECT password_hash FROM users WHERE email = $1", [email.toLowerCase().trim()]);
  if (r.rows.length === 0) console.log("USER NOT FOUND");
  else console.log("PASSWORD MATCH:", await verifyPassword(password, r.rows[0].password_hash));
  await pool.end();
})();