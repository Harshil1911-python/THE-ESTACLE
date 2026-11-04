const fs = require('fs');
const path = require('path');
const Database = require('better-sqlite3');
const bcrypt = require('bcryptjs');

const dataDir = process.env.DATA_DIR || path.join(__dirname, 'data');
fs.mkdirSync(dataDir, { recursive: true });
const dbPath = path.join(dataDir, 'estacle.db');
const db = new Database(dbPath);
db.pragma('journal_mode = WAL');
db.pragma('foreign_keys = ON');

function migrate() {
  db.exec(`
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      email TEXT UNIQUE NOT NULL,
      password TEXT NOT NULL,
      full_name TEXT NOT NULL,
      role TEXT NOT NULL CHECK(role IN ('admin', 'agent', 'customer')),
      phone TEXT,
      created_at TEXT DEFAULT (datetime('now','localtime')),
      is_active INTEGER DEFAULT 1,
      last_seen TEXT
    );
    CREATE TABLE IF NOT EXISTS properties (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT NOT NULL,
      description TEXT,
      price REAL NOT NULL DEFAULT 0,
      property_type TEXT NOT NULL DEFAULT 'apartment',
      status TEXT DEFAULT 'available',
      address TEXT,
      city TEXT,
      state TEXT,
      zip_code TEXT,
      bedrooms INTEGER,
      bathrooms REAL,
      area_sqft REAL,
      agent_id INTEGER,
      created_at TEXT DEFAULT (datetime('now','localtime'))
    );
    CREATE TABLE IF NOT EXISTS clients (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      full_name TEXT NOT NULL,
      email TEXT,
      phone TEXT,
      status TEXT DEFAULT 'lead',
      notes TEXT,
      agent_id INTEGER,
      created_at TEXT DEFAULT (datetime('now','localtime'))
    );
    CREATE TABLE IF NOT EXISTS leads (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      full_name TEXT NOT NULL,
      email TEXT,
      phone TEXT,
      source TEXT,
      interest TEXT,
      budget REAL,
      status TEXT DEFAULT 'new',
      notes TEXT,
      assigned_to INTEGER,
      created_at TEXT DEFAULT (datetime('now','localtime'))
    );
    CREATE TABLE IF NOT EXISTS appointments (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      client_id INTEGER,
      property_id INTEGER,
      agent_id INTEGER,
      appointment_date TEXT,
      status TEXT DEFAULT 'scheduled',
      notes TEXT,
      created_at TEXT DEFAULT (datetime('now','localtime'))
    );
    CREATE TABLE IF NOT EXISTS tasks (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT NOT NULL,
      description TEXT,
      due_date TEXT,
      status TEXT DEFAULT 'pending',
      priority TEXT DEFAULT 'medium',
      assigned_to INTEGER,
      related_client_id INTEGER,
      related_property_id INTEGER,
      created_by INTEGER,
      created_at TEXT DEFAULT (datetime('now','localtime'))
    );
    CREATE TABLE IF NOT EXISTS deals (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT,
      client_id INTEGER,
      property_id INTEGER,
      stage TEXT DEFAULT 'lead',
      value REAL DEFAULT 0,
      agent_id INTEGER,
      notes TEXT,
      created_at TEXT DEFAULT (datetime('now','localtime')),
      updated_at TEXT DEFAULT (datetime('now','localtime'))
    );
    CREATE TABLE IF NOT EXISTS settings (
      key TEXT PRIMARY KEY,
      value TEXT
    );
    CREATE TABLE IF NOT EXISTS activity_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER,
      action TEXT,
      entity_type TEXT,
      entity_id INTEGER,
      details TEXT,
      created_at TEXT DEFAULT (datetime('now','localtime'))
    );
    CREATE TABLE IF NOT EXISTS sessions (
      token TEXT PRIMARY KEY,
      user_id INTEGER NOT NULL,
      created_at TEXT DEFAULT (datetime('now','localtime')),
      expires_at TEXT
    );
  `);

  const count = db.prepare('SELECT COUNT(*) AS c FROM users').get().c;
  if (count === 0) {
    db.prepare(
      `INSERT INTO users (email, password, full_name, role, phone) VALUES (?, ?, ?, ?, ?)`
    ).run('admin@estacle.com', bcrypt.hashSync('admin123', 10), 'Admin User', 'admin', '');
    db.prepare(
      `INSERT INTO users (email, password, full_name, role, phone) VALUES (?, ?, ?, ?, ?)`
    ).run('agent@estacle.com', bcrypt.hashSync('agent123', 10), 'Demo Agent', 'agent', '');
    db.prepare(
      `INSERT INTO users (email, password, full_name, role, phone) VALUES (?, ?, ?, ?, ?)`
    ).run('customer@estacle.com', bcrypt.hashSync('customer123', 10), 'Demo Customer', 'customer', '');
  }

  const set = db.prepare('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)');
  set.run('currency', 'INR');
  set.run('company_name', 'Estacle');
  set.run('connection_mode', 'online');
}

migrate();

function logActivity(userId, action, entityType, entityId, details) {
  db.prepare(
    `INSERT INTO activity_log (user_id, action, entity_type, entity_id, details) VALUES (?, ?, ?, ?, ?)`
  ).run(userId || null, action, entityType || null, entityId || null, details || null);
}

module.exports = { db, logActivity, migrate };
