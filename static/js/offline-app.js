(function () {
  var state = { tab: 'dashboard', pending: 0 };

  function $(id) { return document.getElementById(id); }

  function fmtMoney(n) {
    if (n == null || n === '') return '-';
    try { return 'Rs.' + Number(n).toLocaleString('en-IN'); } catch (e) { return String(n); }
  }

  function setStatus() {
    var online = navigator.onLine;
    var el = $('netPill');
    if (!el) return;
    el.textContent = online ? 'Online' : 'Offline';
    el.className = 'pill ' + (online ? 'on' : 'off');
    $('syncHint').textContent = online
      ? 'Connected — data will sync automatically.'
      : 'Working offline from device storage. Changes queue until you reconnect.';
  }

  async function refreshPendingCount() {
    var list = await EstacleOfflineDB.listPending();
    state.pending = list.length;
    var b = $('pendingBadge');
    if (b) {
      b.textContent = state.pending ? (state.pending + ' pending') : 'Synced';
      b.className = 'pill ' + (state.pending ? 'warn' : 'on');
    }
  }

  async function pullSnapshot() {
    if (!navigator.onLine) return false;
    try {
      var res = await fetch('/api/offline/snapshot', {
        credentials: 'same-origin',
        headers: { 'Accept': 'application/json' }
      });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      var json = await res.json();
      if (!json.ok) throw new Error('Bad snapshot');
      await EstacleOfflineDB.saveSnapshot(json);
      $('lastSync').textContent = 'Last sync: ' + (json.synced_at || 'just now');
      return true;
    } catch (e) {
      console.warn('snapshot failed', e);
      return false;
    }
  }

  async function pushMutations() {
    if (!navigator.onLine) return;
    var pending = await EstacleOfflineDB.listPending();
    if (!pending.length) return;
    try {
      var res = await fetch('/api/offline/sync', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify({ mutations: pending })
      });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      var json = await res.json();
      var done = [];
      (json.results || []).forEach(function (r) {
        if (r.ok) done.push(r.id);
      });
      await EstacleOfflineDB.clearPending(done);
      await pullSnapshot();
    } catch (e) {
      console.warn('sync failed', e);
    }
  }

  async function fullSync() {
    $('syncBtn').disabled = true;
    $('syncBtn').textContent = 'Syncing…';
    await pushMutations();
    await pullSnapshot();
    await refreshPendingCount();
    await render();
    $('syncBtn').disabled = false;
    $('syncBtn').textContent = 'Sync now';
    setStatus();
  }

  function navTo(tab) {
    state.tab = tab;
    document.querySelectorAll('.nav-btn').forEach(function (b) {
      b.classList.toggle('active', b.getAttribute('data-tab') === tab);
    });
    render();
  }

  async function render() {
    await refreshPendingCount();
    var root = $('view');
    if (!root) return;
    if (state.tab === 'dashboard') await renderDashboard(root);
    else if (state.tab === 'clients') await renderClients(root);
    else if (state.tab === 'leads') await renderLeads(root);
    else if (state.tab === 'properties') await renderProperties(root);
    else if (state.tab === 'tasks') await renderTasks(root);
    else if (state.tab === 'appointments') await renderAppointments(root);
  }

  async function renderDashboard(root) {
    var clients = await EstacleOfflineDB.getTable('clients');
    var props = await EstacleOfflineDB.getTable('properties');
    var tasks = await EstacleOfflineDB.getTable('tasks');
    var leads = await EstacleOfflineDB.getTable('leads');
    var appts = await EstacleOfflineDB.getTable('appointments');
    root.innerHTML =
      '<div class="grid stats">' +
      card('Clients', clients.length) +
      card('Leads', leads.length) +
      card('Properties', props.length) +
      card('Tasks', tasks.length) +
      card('Appointments', appts.length) +
      card('Pending sync', state.pending) +
      '</div>' +
      '<div class="panel"><h3>Recent clients</h3>' + listTable(
        ['Name', 'Phone', 'Status'],
        clients.slice(0, 8).map(function (c) {
          return [c.full_name, c.phone || '-', c.status || '-'];
        })
      ) + '</div>';
  }

  function card(label, value) {
    return '<div class="stat"><div class="v">' + value + '</div><div class="l">' + label + '</div></div>';
  }

  function listTable(headers, rows) {
    if (!rows.length) return '<p class="empty">No records in offline storage yet. Sync while online first.</p>';
    var h = '<table><thead><tr>' + headers.map(function (x) { return '<th>' + x + '</th>'; }).join('') + '</tr></thead><tbody>';
    h += rows.map(function (r) {
      return '<tr>' + r.map(function (c) { return '<td>' + escapeHtml(c) + '</td>'; }).join('') + '</tr>';
    }).join('');
    return h + '</tbody></table>';
  }

  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  async function renderClients(root) {
    var clients = await EstacleOfflineDB.getTable('clients');
    root.innerHTML =
      '<div class="panel">' +
      '<div class="row-between"><h3>Clients</h3><button class="btn" id="addClientBtn">+ Add offline</button></div>' +
      '<div id="addClientForm" class="form hidden">' +
      '<input id="cName" placeholder="Full name" />' +
      '<input id="cPhone" placeholder="Phone" />' +
      '<input id="cEmail" placeholder="Email" />' +
      '<button class="btn primary" id="saveClientBtn">Save locally</button></div>' +
      listTable(['Name', 'Phone', 'Email', 'Status'], clients.map(function (c) {
        return [c.full_name, c.phone || '-', c.email || '-', c.status || '-'];
      })) + '</div>';
    wireClientForm();
  }

  function wireClientForm() {
    var box = $('addClientForm');
    $('addClientBtn').onclick = function () { box.classList.toggle('hidden'); };
    $('saveClientBtn').onclick = async function () {
      var name = ($('cName').value || '').trim();
      if (!name) { alert('Name required'); return; }
      var data = {
        full_name: name,
        phone: $('cPhone').value.trim(),
        email: $('cEmail').value.trim(),
        status: 'lead'
      };
      await EstacleOfflineDB.addLocalRow('clients', data);
      await EstacleOfflineDB.queueMutation('clients', 'create', data);
      await render();
      if (navigator.onLine) await fullSync();
    };
  }

  async function renderLeads(root) {
    var leads = await EstacleOfflineDB.getTable('leads');
    root.innerHTML =
      '<div class="panel">' +
      '<div class="row-between"><h3>Leads</h3><button class="btn" id="addLeadBtn">+ Add offline</button></div>' +
      '<div id="addLeadForm" class="form hidden">' +
      '<input id="lName" placeholder="Full name" />' +
      '<input id="lPhone" placeholder="Phone" />' +
      '<input id="lEmail" placeholder="Email" />' +
      '<button class="btn primary" id="saveLeadBtn">Save locally</button></div>' +
      listTable(['Name', 'Phone', 'Status'], leads.map(function (l) {
        return [l.full_name, l.phone || '-', l.status || '-'];
      })) + '</div>';
    $('addLeadBtn').onclick = function () { $('addLeadForm').classList.toggle('hidden'); };
    $('saveLeadBtn').onclick = async function () {
      var name = ($('lName').value || '').trim();
      if (!name) { alert('Name required'); return; }
      var data = { full_name: name, phone: $('lPhone').value.trim(), email: $('lEmail').value.trim(), status: 'new', source: 'offline' };
      await EstacleOfflineDB.addLocalRow('leads', data);
      await EstacleOfflineDB.queueMutation('leads', 'create', data);
      await render();
      if (navigator.onLine) await fullSync();
    };
  }

  async function renderProperties(root) {
    var props = await EstacleOfflineDB.getTable('properties');
    root.innerHTML =
      '<div class="panel"><h3>Properties</h3>' +
      listTable(['Title', 'City', 'Price', 'Status'], props.map(function (p) {
        return [p.title, p.city || '-', fmtMoney(p.price), p.status || '-'];
      })) + '</div>';
  }

  async function renderTasks(root) {
    var tasks = await EstacleOfflineDB.getTable('tasks');
    root.innerHTML =
      '<div class="panel">' +
      '<div class="row-between"><h3>Tasks</h3><button class="btn" id="addTaskBtn">+ Add offline</button></div>' +
      '<div id="addTaskForm" class="form hidden">' +
      '<input id="tTitle" placeholder="Task title" />' +
      '<select id="tPriority"><option value="low">Low</option><option value="medium" selected>Medium</option><option value="high">High</option></select>' +
      '<button class="btn primary" id="saveTaskBtn">Save locally</button></div>' +
      listTable(['Title', 'Status', 'Priority', 'Due'], tasks.map(function (t) {
        return [t.title, t.status || '-', t.priority || '-', t.due_date || '-'];
      })) + '</div>';
    $('addTaskBtn').onclick = function () { $('addTaskForm').classList.toggle('hidden'); };
    $('saveTaskBtn').onclick = async function () {
      var title = ($('tTitle').value || '').trim();
      if (!title) { alert('Title required'); return; }
      var data = { title: title, priority: $('tPriority').value, status: 'pending' };
      await EstacleOfflineDB.addLocalRow('tasks', data);
      await EstacleOfflineDB.queueMutation('tasks', 'create', data);
      await render();
      if (navigator.onLine) await fullSync();
    };
  }

  async function renderAppointments(root) {
    var appts = await EstacleOfflineDB.getTable('appointments');
    var clients = await EstacleOfflineDB.getTable('clients');
    var cmap = {};
    clients.forEach(function (c) { cmap[c.id] = c.full_name; });
    root.innerHTML =
      '<div class="panel"><h3>Appointments</h3>' +
      listTable(['When', 'Client', 'Status'], appts.map(function (a) {
        return [a.appointment_date || '-', cmap[a.client_id] || ('#' + (a.client_id || '-')), a.status || '-'];
      })) + '</div>';
  }

  function boot() {
    setStatus();
    document.querySelectorAll('.nav-btn').forEach(function (b) {
      b.addEventListener('click', function () { navTo(b.getAttribute('data-tab')); });
    });
    $('syncBtn').addEventListener('click', fullSync);
    window.addEventListener('online', function () {
      setStatus();
      fullSync();
    });
    window.addEventListener('offline', setStatus);

    (async function () {
      if (navigator.onLine) {
        await pullSnapshot();
        await pushMutations();
      }
      var synced = await EstacleOfflineDB.getMeta('synced_at');
      $('lastSync').textContent = synced ? ('Last sync: ' + synced) : 'No snapshot yet — connect once to download data.';
      await render();
      await refreshPendingCount();
    })();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
