(function () {
  const root = document.getElementById('app');
  let currentUser = null;
  let page = 'dashboard';

  function money(n) { try { return 'Rs.' + Number(n || 0).toLocaleString('en-IN'); } catch (e) { return String(n); } }
  function esc(s) { return String(s == null ? '' : s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
  function netPill() { return navigator.onLine ? '<span class="pill on">Online</span>' : '<span class="pill off">Offline</span>'; }
  async function pendingPill() {
    const p = await IDB.listPending();
    return p.length ? '<span class="pill off">' + p.length + ' pending</span>' : '<span class="pill on">Synced</span>';
  }
  function nav(id, label) {
    return '<button class="nav-item ' + (page === id ? 'active' : '') + '" data-page="' + id + '">' + label + '</button>';
  }
  function shell(content) {
    return '<div class="layout"><aside class="sidebar"><div class="logo">Estacle <span>CRM</span></div>'
      + nav('dashboard','Dashboard') + nav('clients','Clients') + nav('leads','Leads') + nav('properties','Properties')
      + nav('tasks','Tasks') + nav('appointments','Appointments') + nav('deals','Deals') + nav('settings','Settings')
      + '<div class="sidebar-foot"><button class="nav-item" id="syncBtn">Sync now</button>'
      + '<button class="nav-item" id="logoutBtn">Log out</button></div></aside>'
      + '<main class="main">' + content + '</main></div>';
  }
  function table(headers, rows) {
    if (!rows.length) return '<p class="empty">No records yet.</p>';
    return '<table><thead><tr>' + headers.map(function (h) { return '<th>' + h + '</th>'; }).join('') + '</tr></thead><tbody>'
      + rows.map(function (r) { return '<tr>' + r.map(function (c) { return '<td>' + esc(c) + '</td>'; }).join('') + '</tr>'; }).join('')
      + '</tbody></table>';
  }
  function stat(l, v) { return '<div class="card"><div class="v">' + esc(v) + '</div><div class="l">' + esc(l) + '</div></div>'; }

  async function renderLogin(err) {
    root.innerHTML = '<div class="login-wrap"><div class="login-card"><h1>Estacle</h1>'
      + '<p class="sub">Sign in to your CRM</p>'
      + (err ? '<div class="err">' + esc(err) + '</div>' : '')
      + '<div class="form-grid" style="grid-template-columns:1fr;margin-top:14px">'
      + '<input id="email" type="email" placeholder="Email" value="admin@estacle.com" />'
      + '<input id="password" type="password" placeholder="Password" value="admin123" />'
      + '<button class="btn primary" id="loginBtn">Sign in</button></div>'
      + '<p class="sub" style="margin-top:12px">Demo: admin@estacle.com / admin123</p></div></div>';
    document.getElementById('loginBtn').onclick = async function () {
      try {
        if (!navigator.onLine) {
          var cached = API.user();
          if (cached) { currentUser = cached; await route('dashboard'); return; }
          throw new Error('Offline and no saved session. Connect once to sign in.');
        }
        currentUser = await API.login(document.getElementById('email').value.trim(), document.getElementById('password').value);
        try { await API.snapshot(); } catch (e) {}
        await route('dashboard');
      } catch (e) { renderLogin(e.message || 'Login failed'); }
    };
  }

  function bindShell() {
    document.querySelectorAll('[data-page]').forEach(function (btn) {
      btn.onclick = function () { route(btn.getAttribute('data-page')); };
    });
    var syncBtn = document.getElementById('syncBtn');
    if (syncBtn) syncBtn.onclick = async function () {
      if (!navigator.onLine) { alert('Connect to sync.'); return; }
      syncBtn.textContent = 'Syncing...';
      try { await API.pushPending(); await API.snapshot(); await route(page); }
      catch (e) { alert(e.message || 'Sync failed'); syncBtn.textContent = 'Sync now'; }
    };
    var logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) logoutBtn.onclick = async function () { await API.logout(); currentUser = null; renderLogin(); };
  }

  async function renderDashboard() {
    var data = await API.dashboard();
    var s = data.stats || {};
    root.innerHTML = shell(
      '<div class="topbar"><div><h1>Dashboard</h1><div class="sub">Welcome' + (currentUser ? ', ' + esc(currentUser.full_name) : '') + '</div></div>'
      + '<div class="pills">' + netPill() + ' ' + await pendingPill() + '</div></div>'
      + '<div class="grid">' + stat('Clients', s.total_clients) + stat('Leads', s.total_leads) + stat('Properties', s.total_properties)
      + stat('Available', s.available_properties) + stat('Tasks', s.total_tasks) + stat('Appointments', s.total_appointments)
      + stat('Deals', s.total_deals) + stat('Property value', money(s.property_value)) + '</div>'
      + '<div class="panel"><h3>Recent clients</h3>' + table(['Name','Phone','Status'], (data.recent_clients || []).map(function (c) { return [c.full_name, c.phone || '-', c.status || '-']; })) + '</div>'
    );
    bindShell();
  }

  async function renderCrud(title, tableName, headers, mapRow, fieldsHtml, buildPayload) {
    var rows = await API.list(tableName);
    root.innerHTML = shell(
      '<div class="topbar"><div><h1>' + title + '</h1><div class="sub">' + rows.length + ' records · works offline</div></div>'
      + '<div class="pills">' + netPill() + ' ' + await pendingPill() + '</div></div>'
      + '<div class="panel"><h3>Add</h3><div class="form-grid" id="createForm">' + fieldsHtml + '</div>'
      + '<button class="btn primary" id="saveBtn">Save</button></div>'
      + '<div class="panel"><h3>All</h3>' + table(headers, rows.map(mapRow)) + '</div>'
    );
    bindShell();
    document.getElementById('saveBtn').onclick = async function () {
      try { await API.create(tableName, buildPayload()); await route(page); }
      catch (e) { alert(e.message || 'Save failed'); }
    };
  }

  async function renderClients() {
    await renderCrud('Clients', 'clients', ['Name','Phone','Email','Status'],
      function (c) { return [c.full_name, c.phone || '-', c.email || '-', c.status || '-']; },
      '<input id="f_name" placeholder="Full name" /><input id="f_phone" placeholder="Phone" /><input id="f_email" placeholder="Email" />',
      function () {
        var full_name = document.getElementById('f_name').value.trim();
        if (!full_name) throw new Error('Name required');
        return { full_name: full_name, phone: document.getElementById('f_phone').value.trim(), email: document.getElementById('f_email').value.trim(), status: 'lead' };
      });
  }
  async function renderLeads() {
    await renderCrud('Leads', 'leads', ['Name','Phone','Status','Source'],
      function (c) { return [c.full_name, c.phone || '-', c.status || '-', c.source || '-']; },
      '<input id="f_name" placeholder="Full name" /><input id="f_phone" placeholder="Phone" /><input id="f_source" placeholder="Source" value="web" />',
      function () {
        var full_name = document.getElementById('f_name').value.trim();
        if (!full_name) throw new Error('Name required');
        return { full_name: full_name, phone: document.getElementById('f_phone').value.trim(), source: document.getElementById('f_source').value.trim(), status: 'new' };
      });
  }
  async function renderProperties() {
    await renderCrud('Properties', 'properties', ['Title','City','Price','Status'],
      function (p) { return [p.title, p.city || '-', money(p.price), p.status || '-']; },
      '<input id="f_title" placeholder="Title" /><input id="f_city" placeholder="City" /><input id="f_price" type="number" placeholder="Price" />',
      function () {
        var title = document.getElementById('f_title').value.trim();
        if (!title) throw new Error('Title required');
        return { title: title, city: document.getElementById('f_city').value.trim(), price: document.getElementById('f_price').value, status: 'available', property_type: 'apartment' };
      });
  }
  async function renderTasks() {
    await renderCrud('Tasks', 'tasks', ['Title','Status','Priority','Due'],
      function (t) { return [t.title, t.status || '-', t.priority || '-', t.due_date || '-']; },
      '<input id="f_title" placeholder="Task title" /><select id="f_priority"><option value="low">Low</option><option value="medium" selected>Medium</option><option value="high">High</option></select><input id="f_due" type="date" />',
      function () {
        var title = document.getElementById('f_title').value.trim();
        if (!title) throw new Error('Title required');
        return { title: title, priority: document.getElementById('f_priority').value, due_date: document.getElementById('f_due').value, status: 'pending' };
      });
  }
  async function renderAppointments() {
    var rows = await API.list('appointments');
    var clients = await API.list('clients');
    var map = {}; clients.forEach(function (c) { map[c.id] = c.full_name; });
    root.innerHTML = shell('<div class="topbar"><div><h1>Appointments</h1></div><div class="pills">' + netPill() + '</div></div><div class="panel">'
      + table(['When','Client','Status'], rows.map(function (a) { return [a.appointment_date || '-', map[a.client_id] || '-', a.status || '-']; })) + '</div>');
    bindShell();
  }
  async function renderDeals() {
    var rows = await API.list('deals');
    root.innerHTML = shell('<div class="topbar"><div><h1>Deals</h1></div><div class="pills">' + netPill() + '</div></div><div class="panel">'
      + table(['Title','Stage','Value'], rows.map(function (d) { return [d.title || '-', d.stage || '-', money(d.value)]; })) + '</div>');
    bindShell();
  }
  async function renderSettings() {
    root.innerHTML = shell('<div class="topbar"><div><h1>Settings</h1></div><div class="pills">' + netPill() + '</div></div>'
      + '<div class="panel"><p class="sub">Settings save when online. Offline mode is automatic when Wi-Fi drops.</p></div>');
    bindShell();
  }

  async function route(name) {
    page = name || 'dashboard';
    if (!currentUser) {
      currentUser = API.user();
      if (!currentUser) return renderLogin();
      if (navigator.onLine) {
        try { currentUser = await API.me(); } catch (e) { API.clearSession(); currentUser = null; return renderLogin('Session expired.'); }
      }
    }
    var pages = { dashboard: renderDashboard, clients: renderClients, leads: renderLeads, properties: renderProperties, tasks: renderTasks, appointments: renderAppointments, deals: renderDeals, settings: renderSettings };
    await (pages[page] || renderDashboard)();
  }

  window.addEventListener('online', async function () {
    try { await API.pushPending(); await API.snapshot(); } catch (e) {}
    if (currentUser) route(page);
  });
  window.addEventListener('offline', function () { if (currentUser) route(page); });

  (async function () {
    currentUser = API.user();
    if (currentUser) {
      if (navigator.onLine) {
        try { currentUser = await API.me(); await API.snapshot(); await API.pushPending(); } catch (e) {}
      }
      await route('dashboard');
    } else renderLogin();
  })();
})();
