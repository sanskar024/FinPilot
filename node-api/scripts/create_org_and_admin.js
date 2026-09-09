// One-time bootstrap: creates the first organization and its admin user.
// Run this from a machine with DATABASE_URL set — it is NOT an HTTP
// endpoint and is never exposed over the network, precisely because it
// can create an org + an admin with no authentication check. After this,
// use POST /api/auth/register (for regular users under an existing org)
// and the admin-only POST /api/organizations for any further orgs.
//
// Usage:
//   node scripts/create_org_and_admin.js "My Company" admin@example.com "a-strong-password"

require("dotenv").config();
const pool = require("../db");
const { hashPassword } = require("../auth");

async function main() {
  const [, , orgName, email, password] = process.argv;

  if (!orgName || !email || !password) {
    console.error('Usage: node scripts/create_org_and_admin.js "Org Name" email password');
    process.exit(1);
  }
  if (password.length < 8) {
    console.error("Password must be at least 8 characters.");
    process.exit(1);
  }

  const client = await pool.connect();
  try {
    await client.query("BEGIN");

    const orgResult = await client.query(
      "INSERT INTO organizations (name) VALUES ($1) RETURNING id, name",
      [orgName.trim()]
    );
    const org = orgResult.rows[0];

    const passwordHash = await hashPassword(password);
    const userResult = await client.query(
      `INSERT INTO users (email, password_hash, organization_id, role)
       VALUES ($1, $2, $3, 'admin')
       RETURNING id, email`,
      [email.toLowerCase().trim(), passwordHash, org.id]
    );
    const user = userResult.rows[0];

    await client.query("COMMIT");

    console.log(`Created organization '${org.name}' (id=${org.id})`);
    console.log(`Created admin user '${user.email}' (id=${user.id})`);
    console.log("You can now log in via POST /api/auth/login with this email/password.");
  } catch (err) {
    await client.query("ROLLBACK");
    console.error("Failed:", err.message);
    process.exit(1);
  } finally {
    client.release();
    await pool.end();
  }
}

main();
