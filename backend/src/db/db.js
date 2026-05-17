const { createClient } = require('@libsql/client');
const path = require('path');
const fs = require('fs');

const DATA_DIR = path.join(__dirname, '../../data');
fs.mkdirSync(DATA_DIR, { recursive: true });

const DB_PATH = path.join(DATA_DIR, 'seller.db');

const db = createClient({
  url: `file:${DB_PATH}`,
});

// Read and apply schema on startup
async function initDb() {
  const schemaPath = path.join(__dirname, 'schema.sql');
  const schema = fs.readFileSync(schemaPath, 'utf8');
  // Split on semicolons to run each statement separately
  const statements = schema
    .split(';')
    .map(s => s.trim())
    .filter(s => s.length > 0);

  for (const stmt of statements) {
    await db.execute(stmt);
  }

  // Migrations: add new columns to existing tables if they don't exist yet
  const migrations = [
    `ALTER TABLE videos ADD COLUMN fba_shipment_id TEXT REFERENCES fba_shipments(shipment_id)`,
    `ALTER TABLE videos ADD COLUMN fba_box_number INTEGER`,
  ];
  for (const m of migrations) {
    try { await db.execute(m); } catch (_) { /* column already exists — safe to ignore */ }
  }
}

module.exports = { db, initDb };
