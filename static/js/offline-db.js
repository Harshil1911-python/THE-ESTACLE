/** IndexedDB store for Estacle offline CRM */
(function (global) {
  var DB_NAME = 'estacle_offline';
  var DB_VER = 1;

  function openDb() {
    return new Promise(function (resolve, reject) {
      var req = indexedDB.open(DB_NAME, DB_VER);
      req.onupgradeneeded = function (e) {
        var db = e.target.result;
        if (!db.objectStoreNames.contains('meta')) db.createObjectStore('meta');
        if (!db.objectStoreNames.contains('tables')) db.createObjectStore('tables');
        if (!db.objectStoreNames.contains('pending')) {
          var p = db.createObjectStore('pending', { keyPath: 'id', autoIncrement: true });
          p.createIndex('by_entity', 'entity', { unique: false });
        }
      };
      req.onsuccess = function () { resolve(req.result); };
      req.onerror = function () { reject(req.error); };
    });
  }

  function txDone(tx) {
    return new Promise(function (resolve, reject) {
      tx.oncomplete = function () { resolve(); };
      tx.onerror = function () { reject(tx.error); };
      tx.onabort = function () { reject(tx.error || new Error('aborted')); };
    });
  }

  async function setMeta(key, value) {
    var db = await openDb();
    var tx = db.transaction('meta', 'readwrite');
    tx.objectStore('meta').put(value, key);
    await txDone(tx);
  }

  async function getMeta(key) {
    var db = await openDb();
    return new Promise(function (resolve, reject) {
      var tx = db.transaction('meta', 'readonly');
      var req = tx.objectStore('meta').get(key);
      req.onsuccess = function () { resolve(req.result); };
      req.onerror = function () { reject(req.error); };
    });
  }

  async function saveSnapshot(snapshot) {
    var db = await openDb();
    var tx = db.transaction(['tables', 'meta'], 'readwrite');
    var tables = tx.objectStore('tables');
    var data = snapshot.data || {};
    Object.keys(data).forEach(function (k) {
      tables.put(data[k], k);
    });
    tx.objectStore('meta').put(snapshot.synced_at || new Date().toISOString(), 'synced_at');
    tx.objectStore('meta').put(snapshot.user || null, 'user');
    await txDone(tx);
  }

  async function getTable(name) {
    var db = await openDb();
    return new Promise(function (resolve, reject) {
      var tx = db.transaction('tables', 'readonly');
      var req = tx.objectStore('tables').get(name);
      req.onsuccess = function () { resolve(req.result || []); };
      req.onerror = function () { reject(req.error); };
    });
  }

  async function queueMutation(entity, action, data) {
    var db = await openDb();
    var tx = db.transaction('pending', 'readwrite');
    var rec = {
      entity: entity,
      action: action,
      data: data,
      created_at: new Date().toISOString()
    };
    var req = tx.objectStore('pending').add(rec);
    await txDone(tx);
    return req.result;
  }

  async function listPending() {
    var db = await openDb();
    return new Promise(function (resolve, reject) {
      var tx = db.transaction('pending', 'readonly');
      var req = tx.objectStore('pending').getAll();
      req.onsuccess = function () { resolve(req.result || []); };
      req.onerror = function () { reject(req.error); };
    });
  }

  async function clearPending(ids) {
    if (!ids || !ids.length) return;
    var db = await openDb();
    var tx = db.transaction('pending', 'readwrite');
    var store = tx.objectStore('pending');
    ids.forEach(function (id) { store.delete(id); });
    await txDone(tx);
  }

  async function addLocalRow(table, row) {
    var rows = await getTable(table);
    rows = rows.slice();
    row._local = true;
    row.id = row.id || ('local_' + Date.now());
    rows.unshift(row);
    var db = await openDb();
    var tx = db.transaction('tables', 'readwrite');
    tx.objectStore('tables').put(rows, table);
    await txDone(tx);
    return row;
  }

  async function updateLocalRow(table, id, patch) {
    var rows = await getTable(table);
    rows = rows.map(function (r) {
      if (String(r.id) === String(id)) return Object.assign({}, r, patch);
      return r;
    });
    var db = await openDb();
    var tx = db.transaction('tables', 'readwrite');
    tx.objectStore('tables').put(rows, table);
    await txDone(tx);
  }

  global.EstacleOfflineDB = {
    saveSnapshot: saveSnapshot,
    getTable: getTable,
    getMeta: getMeta,
    setMeta: setMeta,
    queueMutation: queueMutation,
    listPending: listPending,
    clearPending: clearPending,
    addLocalRow: addLocalRow,
    updateLocalRow: updateLocalRow
  };
})(window);
