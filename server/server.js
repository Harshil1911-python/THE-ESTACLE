const path = require('path');
const express = require('express');
const cookieParser = require('cookie-parser');
const cors = require('cors');
const bcrypt = require('bcryptjs');
const { v4: uuidv4 } = require('uuid');
const { db, logActivity } = require('./db');

const app = express();
const PORT = process.env.PORT || 5001;

app.use(cors({ origin: true, credentials: true }));
app.use(express.json({ limit: '2mb' }));
app.use(cookieParser());
app.use(express.static(path.join(__dirname, 'public'), { maxAge: '1h' }));

function auth(req, res, next) {
  const header = req.headers.authorization || '';
  const bearer = header.startsWith('Bearer ') ? header.slice(7) : null;
  const token = bearer || req.cookies.estacle_token || req.headers['x-session-token'];
  if (!token) return res.status(401).json({ error: 'Unauthorized' });
  const session = db.get('sessions', (s) => s.token === token);
  if (!session) return res.status(401).json({ error: 'Unauthorized' });
  const user = db.get('users', (u) => u.id === session.user_id && u.is_active);
  if (!user) return res.status(401).json({ error: 'Unauthorized' });
  req.user = user;
  req.token = token;
  next();
}

function requireRole(...roles) {
  return (req, res, next) => {
    if (!req.user || !roles.includes(req.user.role)) return res.status(403).json({ error: 'Forbidden' });
    next();
  };
}

app.post('/api/auth/login', (req, res) => {
  const email = String(req.body.email || '').trim().toLowerCase();
  const password = String(req.body.password || '');
  const user = db.get('users', (u) => u.email === email);
  if (!user || !user.is_active || !bcrypt.compareSync(password, user.password)) {
    return res.status(401).json({ error: 'Invalid email or password' });
  }
  const token = uuidv4();
  db.insert('sessions', { token, user_id: user.id });
  db.update('users', user.id, { last_seen: new Date().toISOString() });
  logActivity(user.id, 'Login', 'user', user.id, null);
  res.cookie('estacle_token', token, { httpOnly: false, sameSite: 'lax', maxAge: 30 * 864e5 });
  res.json({ ok: true, token, user: { id: user.id, email: user.email, full_name: user.full_name, role: user.role } });
});

app.post('/api/auth/logout', auth, (req, res) => {
  db.remove('sessions', (s) => s.token === req.token);
  res.clearCookie('estacle_token');
  res.json({ ok: true });
});

app.get('/api/auth/me', auth, (req, res) => {
  res.json({ ok: true, user: { id: req.user.id, email: req.user.email, full_name: req.user.full_name, role: req.user.role } });
});

app.get('/api/offline/snapshot', auth, requireRole('admin', 'agent'), (req, res) => {
  res.json({
    ok: true,
    synced_at: new Date().toISOString(),
    user: { id: req.user.id, role: req.user.role, name: req.user.full_name },
    data: {
      clients: db.all('clients'),
      properties: db.all('properties'),
      leads: db.all('leads'),
      tasks: db.all('tasks'),
      appointments: db.all('appointments'),
      deals: db.all('deals'),
      users: db.all('users').map((u) => ({ id: u.id, email: u.email, full_name: u.full_name, role: u.role, phone: u.phone, is_active: u.is_active, created_at: u.created_at })),
      settings: db.raw().settings || [],
    },
  });
});

app.post('/api/offline/sync', auth, requireRole('admin', 'agent'), (req, res) => {
  const mutations = req.body.mutations || [];
  const results = [];
  const uid = req.user.id;
  for (const m of mutations) {
    try {
      const data = m.data || {};
      if (m.entity === 'clients' && m.action === 'create') {
        const id = db.insert('clients', { full_name: data.full_name || 'Client', email: data.email || null, phone: data.phone || null, status: data.status || 'lead', notes: data.notes || null, agent_id: data.agent_id || uid });
        results.push({ id: m.id, ok: true, server_id: id });
      } else if (m.entity === 'leads' && m.action === 'create') {
        const id = db.insert('leads', { full_name: data.full_name || 'Lead', email: data.email || null, phone: data.phone || null, source: data.source || 'offline', status: data.status || 'new', notes: data.notes || null, assigned_to: uid });
        results.push({ id: m.id, ok: true, server_id: id });
      } else if (m.entity === 'tasks' && m.action === 'create') {
        const id = db.insert('tasks', { title: data.title || 'Task', description: data.description || null, due_date: data.due_date || null, status: data.status || 'pending', priority: data.priority || 'medium', assigned_to: uid, created_by: uid });
        results.push({ id: m.id, ok: true, server_id: id });
      } else if (m.entity === 'properties' && m.action === 'create') {
        const id = db.insert('properties', { title: data.title || 'Property', description: data.description || null, price: Number(data.price) || 0, property_type: data.property_type || 'apartment', status: data.status || 'available', city: data.city || null, address: data.address || null, agent_id: uid });
        results.push({ id: m.id, ok: true, server_id: id });
      } else {
        results.push({ id: m.id, ok: false, error: 'unsupported' });
      }
    } catch (e) {
      results.push({ id: m.id, ok: false, error: String(e.message || e) });
    }
  }
  res.json({ ok: true, results });
});

app.get('/api/dashboard', auth, requireRole('admin', 'agent'), (req, res) => {
  const properties = db.all('properties');
  const deals = db.all('deals');
  res.json({
    ok: true,
    stats: {
      total_users: db.all('users').length,
      total_agents: db.all('users').filter((u) => u.role === 'agent').length,
      total_properties: properties.length,
      available_properties: properties.filter((p) => p.status === 'available').length,
      total_clients: db.all('clients').length,
      total_leads: db.all('leads').length,
      total_tasks: db.all('tasks').length,
      total_appointments: db.all('appointments').length,
      total_deals: deals.length,
      property_value: properties.reduce((s, p) => s + (Number(p.price) || 0), 0),
      deal_value: deals.reduce((s, p) => s + (Number(p.value) || 0), 0),
    },
    recent_clients: db.all('clients').slice(0, 8),
    recent_activity: db.all('activity_log').slice(0, 12),
  });
});

['clients', 'properties', 'leads', 'tasks', 'appointments', 'deals'].forEach((table) => {
  app.get(`/api/${table}`, auth, requireRole('admin', 'agent'), (req, res) => {
    res.json({ ok: true, rows: db.all(table) });
  });
});

app.post('/api/clients', auth, requireRole('admin', 'agent'), (req, res) => {
  const d = req.body || {};
  const id = db.insert('clients', { full_name: d.full_name, email: d.email || null, phone: d.phone || null, status: d.status || 'lead', notes: d.notes || null, agent_id: d.agent_id || req.user.id });
  logActivity(req.user.id, 'Created client', 'client', id, d.full_name);
  res.json({ ok: true, id });
});

app.post('/api/leads', auth, requireRole('admin', 'agent'), (req, res) => {
  const d = req.body || {};
  const id = db.insert('leads', { full_name: d.full_name, email: d.email || null, phone: d.phone || null, source: d.source || null, interest: d.interest || null, budget: d.budget || null, status: d.status || 'new', notes: d.notes || null, assigned_to: d.assigned_to || req.user.id });
  res.json({ ok: true, id });
});

app.post('/api/properties', auth, requireRole('admin', 'agent'), (req, res) => {
  const d = req.body || {};
  const id = db.insert('properties', { title: d.title, description: d.description || null, price: Number(d.price) || 0, property_type: d.property_type || 'apartment', status: d.status || 'available', address: d.address || null, city: d.city || null, state: d.state || null, bedrooms: d.bedrooms || null, bathrooms: d.bathrooms || null, area_sqft: d.area_sqft || null, agent_id: d.agent_id || req.user.id });
  res.json({ ok: true, id });
});

app.post('/api/tasks', auth, requireRole('admin', 'agent'), (req, res) => {
  const d = req.body || {};
  const id = db.insert('tasks', { title: d.title, description: d.description || null, due_date: d.due_date || null, status: d.status || 'pending', priority: d.priority || 'medium', assigned_to: d.assigned_to || req.user.id, created_by: req.user.id });
  res.json({ ok: true, id });
});

app.get('/api/settings', auth, requireRole('admin'), (req, res) => {
  res.json({ ok: true, settings: db.settingsMap() });
});

app.put('/api/settings', auth, requireRole('admin'), (req, res) => {
  Object.keys(req.body || {}).forEach((k) => db.setting(k, req.body[k]));
  res.json({ ok: true });
});

app.get('/api/activity', auth, requireRole('admin'), (req, res) => {
  res.json({ ok: true, rows: db.all('activity_log') });
});

app.get('/api/users', auth, requireRole('admin'), (req, res) => {
  res.json({ ok: true, rows: db.all('users').map((u) => ({ id: u.id, email: u.email, full_name: u.full_name, role: u.role, phone: u.phone, is_active: u.is_active, created_at: u.created_at, last_seen: u.last_seen })) });
});

app.get('/healthz', (req, res) => res.json({ ok: true, engine: 'node' }));

app.get('*', (req, res) => {
  if (req.path.startsWith('/api/')) return res.status(404).json({ error: 'Not found' });
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, '0.0.0.0', () => {
  console.log('Estacle Node server on :' + PORT);
});
