(function (g) {
  const DB = 'estacle_v2';
  const VER = 1;
  function open() {
    return new Promise((resolve, reject) => {
      const r = indexedDB.open(DB, VER);
      r.onupgradeneeded = (e) => {
        const db = e.target.result;
        if (!db.objectStoreNames.contains('meta')) db.createObjectStore('meta');
        if (!db.objectStoreNames.contains('tables')) db.createObjectStore('tables');
        if (!db.objectStoreNames.contains('pending')) db.createObjectStore('pending', { keyPath: 'id', autoIncrement: true });
      };
      r.onsuccess = () => resolve(r.result);
      r.onerror = () => reject(r.error);
    });
  }
  function done(tx) {
    return new Promise((res, rej) => {
      tx.oncomplete = () => res();
      tx.onerror = () => rej(tx.error);
    });
  }
  async function setMeta(k, v) {
    const db = await open();
    const tx = db.transaction('meta', 'readwrite');
    tx.objectStore('meta').put(v, k);
    await done(tx);
  }
  async function getMeta(k) {
    const db = await open();
    return new Promise((res, rej) => {
      const tx = db.transaction('meta', 'readonly');
      const req = tx.objectStore('meta').get(k);
      req.onsuccess = () => res(req.result);
      req.onerror = () => rej(req.error);
    });
  }
  async function saveTables(data) {
    const db = await open();
    const tx = db.transaction('tables', 'readwrite');
    const st = tx.objectStore('tables');
    Object.keys(data || {}).forEach((k) => st.put(data[k], k));
    await done(tx);
  }
  async function getTable(name) {
    const db = await open();
    return new Promise((res, rej) => {
      const tx = db.transaction('tables', 'readonly');
      const req = tx.objectStore('tables').get(name);
      req.onsuccess = () => res(req.result || []);
      req.onerror = () => rej(req.error);
    });
  }
  async function putTable(name, rows) {
    const db = await open();
    const tx = db.transaction('tables', 'readwrite');
    tx.objectStore('tables').put(rows, name);
    await done(tx);
  }
  async function queue(mut) {
    const db = await open();
    const tx = db.transaction('pending', 'readwrite');
    const req = tx.objectStore('pending').add(Object.assign({ created_at: new Date().toISOString() }, mut));
    await done(tx);
    return req.result;
  }
  async function listPending() {
    const db = await open();
    return new Promise((res, rej) => {
      const tx = db.transaction('pending', 'readonly');
      const req = tx.objectStore('pending').getAll();
      req.onsuccess = () => res(req.result || []);
      req.onerror = () => rej(req.error);
    });
  }
  async function clearPending(ids) {
    if (!ids || !ids.length) return;
    const db = await open();
    const tx = db.transaction('pending', 'readwrite');
    const st = tx.objectStore('pending');
    ids.forEach((id) => st.delete(id));
    await done(tx);
  }
  g.IDB = { setMeta, getMeta, saveTables, getTable, putTable, queue, listPending, clearPending };
})(window);
