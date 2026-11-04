(function (g) {
  function token() {
    try { return localStorage.getItem('estacle_token') || ''; } catch (e) { return ''; }
  }
  function user() {
    try { return JSON.parse(localStorage.getItem('estacle_user') || 'null'); } catch (e) { return null; }
  }
  function setSession(t, u) {
    localStorage.setItem('estacle_token', t);
    localStorage.setItem('estacle_user', JSON.stringify(u));
  }
  function clearSession() {
    localStorage.removeItem('estacle_token');
    localStorage.removeItem('estacle_user');
  }
  async function req(path, opts) {
    opts = opts || {};
    const headers = Object.assign({ 'Accept': 'application/json' }, opts.headers || {});
    if (opts.body && typeof opts.body === 'object' && !(opts.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(opts.body);
    }
    const t = token();
    if (t) headers.Authorization = 'Bearer ' + t;
    const res = await fetch(path, Object.assign({}, opts, { headers, credentials: 'same-origin' }));
    let json = null;
    try { json = await res.json(); } catch (e) {}
    if (!res.ok) {
      const err = new Error((json && json.error) || ('HTTP ' + res.status));
      err.status = res.status;
      err.payload = json;
      throw err;
    }
    return json;
  }

  async function login(email, password) {
    const json = await req('/api/auth/login', { method: 'POST', body: { email, password } });
    setSession(json.token, json.user);
    return json.user;
  }
  async function logout() {
    try { if (navigator.onLine) await req('/api/auth/logout', { method: 'POST', body: {} }); } catch (e) {}
    clearSession();
  }
  async function me() {
    if (!navigator.onLine) return user();
    const json = await req('/api/auth/me');
    setSession(token(), json.user);
    return json.user;
  }
  async function snapshot() {
    const json = await req('/api/offline/snapshot');
    await IDB.saveTables(json.data);
    await IDB.setMeta('synced_at', json.synced_at);
    await IDB.setMeta('user', json.user);
    return json;
  }
  async function pushPending() {
    const pending = await IDB.listPending();
    if (!pending.length || !navigator.onLine) return;
    const json = await req('/api/offline/sync', { method: 'POST', body: { mutations: pending } });
    const done = (json.results || []).filter((r) => r.ok).map((r) => r.id);
    await IDB.clearPending(done);
    await snapshot();
  }
  async function list(table) {
    if (!navigator.onLine) return IDB.getTable(table);
    try {
      const json = await req('/api/' + table);
      await IDB.putTable(table, json.rows || []);
      return json.rows || [];
    } catch (e) {
      return IDB.getTable(table);
    }
  }
  async function create(table, data) {
    if (!navigator.onLine) {
      const rows = await IDB.getTable(table);
      const row = Object.assign({ id: 'local_' + Date.now(), _local: true }, data);
      rows.unshift(row);
      await IDB.putTable(table, rows);
      await IDB.queue({ entity: table, action: 'create', data });
      return row;
    }
    const json = await req('/api/' + table, { method: 'POST', body: data });
    try { await snapshot(); } catch (e) {}
    return json;
  }
  async function dashboard() {
    if (!navigator.onLine) {
      const clients = await IDB.getTable('clients');
      const properties = await IDB.getTable('properties');
      const leads = await IDB.getTable('leads');
      const tasks = await IDB.getTable('tasks');
      const appointments = await IDB.getTable('appointments');
      const deals = await IDB.getTable('deals');
      const users = await IDB.getTable('users');
      return {
        stats: {
          total_users: users.length,
          total_properties: properties.length,
          available_properties: properties.filter((p) => p.status === 'available').length,
          total_clients: clients.length,
          total_leads: leads.length,
          total_tasks: tasks.length,
          total_appointments: appointments.length,
          total_deals: deals.length,
          property_value: properties.reduce((s, p) => s + (Number(p.price) || 0), 0),
          deal_value: deals.reduce((s, p) => s + (Number(p.value) || 0), 0),
        },
        recent_clients: clients.slice(0, 8),
        recent_activity: [],
      };
    }
    return req('/api/dashboard');
  }

  g.API = { token, user, setSession, clearSession, login, logout, me, snapshot, pushPending, list, create, dashboard, req };
})(window);
