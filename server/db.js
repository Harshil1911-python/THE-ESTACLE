const fs = require('fs');
const path = require('path');
const bcrypt = require('bcryptjs');

const dataDir = process.env.DATA_DIR || path.join(__dirname, 'data');
fs.mkdirSync(dataDir, { recursive: true });
const dbPath = path.join(dataDir, 'estacle.json');

const defaultData = () => ({
  users: [], properties: [], clients: [], leads: [], appointments: [], tasks: [], deals: [],
  settings: [
    { key: 'currency', value: 'INR' },
    { key: 'company_name', value: 'Estacle' },
    { key: 'connection_mode', value: 'online' },
  ],
  activity_log: [], sessions: [],
  _seq: { users: 1, properties: 1, clients: 1, leads: 1, appointments: 1, tasks: 1, deals: 1, activity_log: 1 },
});

function load() {
  if (!fs.existsSync(dbPath)) {
    const data = defaultData();
    data.users.push({ id: data._seq.users++, email: 'admin@estacle.com', password: bcrypt.hashSync('admin123', 10), full_name: 'Admin User', role: 'admin', phone: '', created_at: new Date().toISOString(), is_active: 1 });
    data.users.push({ id: data._seq.users++, email: 'agent@estacle.com', password: bcrypt.hashSync('agent123', 10), full_name: 'Demo Agent', role: 'agent', phone: '', created_at: new Date().toISOString(), is_active: 1 });
    save(data);
    return data;
  }
  return JSON.parse(fs.readFileSync(dbPath, 'utf8'));
}
function save(data) { fs.writeFileSync(dbPath, JSON.stringify(data, null, 2)); }
let state = load();

const db = {
  all(table) { return (state[table] || []).slice().sort((a, b) => (b.id || 0) - (a.id || 0)); },
  get(table, pred) { return (state[table] || []).find(pred) || null; },
  insert(table, row) {
    if (!state._seq[table]) state._seq[table] = 1;
    row.id = state._seq[table]++;
    if (!row.created_at) row.created_at = new Date().toISOString();
    state[table] = state[table] || [];
    state[table].push(row);
    save(state);
    return row.id;
  },
  update(table, id, patch) {
    const rows = state[table] || [];
    const i = rows.findIndex((r) => String(r.id) === String(id));
    if (i < 0) return false;
    rows[i] = Object.assign({}, rows[i], patch);
    save(state);
    return true;
  },
  remove(table, pred) { state[table] = (state[table] || []).filter((r) => !pred(r)); save(state); },
  setting(key, value) {
    if (value === undefined) {
      const row = (state.settings || []).find((s) => s.key === key);
      return row ? row.value : null;
    }
    const rows = state.settings || [];
    const i = rows.findIndex((s) => s.key === key);
    if (i >= 0) rows[i].value = String(value);
    else rows.push({ key, value: String(value) });
    state.settings = rows;
    save(state);
  },
  settingsMap() {
    const map = {};
    (state.settings || []).forEach((s) => { map[s.key] = s.value; });
    return map;
  },
  raw: () => state,
};

function logActivity(userId, action, entityType, entityId, details) {
  db.insert('activity_log', { user_id: userId || null, action, entity_type: entityType || null, entity_id: entityId || null, details: details || null });
}

module.exports = { db, logActivity };
