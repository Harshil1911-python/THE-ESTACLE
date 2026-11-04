(function () {
  if (window.__estacleNetInit) return;
  window.__estacleNetInit = true;

  var BANNER_ID = 'estacle-net-banner';

  function ensureBanner() {
    var el = document.getElementById(BANNER_ID);
    if (el) return el;
    el = document.createElement('div');
    el.id = BANNER_ID;
    el.setAttribute('role', 'status');
    el.style.cssText = [
      'position:fixed', 'top:0', 'left:0', 'right:0', 'z-index:99999',
      'padding:10px 16px', 'text-align:center', 'font:600 13px/1.4 Inter,system-ui,sans-serif',
      'background:#9a3412', 'color:#fff7ed', 'display:none',
      'box-shadow:0 4px 16px rgba(0,0,0,.18)'
    ].join(';');
    el.textContent = 'You are offline — Estacle is in offline mode. Changes stay local until you reconnect.';
    document.body.appendChild(el);
    return el;
  }

  function setClientOffline(offline) {
    try {
      localStorage.setItem('estacle_net', offline ? 'offline' : 'online');
      localStorage.setItem('estacle_auto_offline', offline ? '1' : '0');
    } catch (e) {}
    var banner = ensureBanner();
    if (offline) {
      banner.style.display = 'block';
      document.documentElement.classList.add('estacle-offline');
      if (document.body) document.body.style.paddingTop = '40px';
    } else {
      banner.style.display = 'none';
      document.documentElement.classList.remove('estacle-offline');
      if (document.body) document.body.style.paddingTop = '';
    }
  }

  function notifyServerMode(mode) {
    try {
      var body = new URLSearchParams();
      body.set('connection_mode', mode);
      fetch('/admin/settings/connection', {
        method: 'POST',
        body: body,
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        keepalive: true,
        redirect: 'manual'
      }).catch(function () {});
    } catch (e) {}
  }

  function goOffline() {
    setClientOffline(true);
    notifyServerMode('offline');
  }

  function goOnline() {
    setClientOffline(false);
    notifyServerMode('online');
    try { localStorage.setItem('estacle_auto_offline', '0'); } catch (e) {}
  }

  function syncFromNavigator() {
    if (typeof navigator.onLine === 'boolean' && !navigator.onLine) {
      goOffline();
    } else {
      goOnline();
    }
  }

  window.addEventListener('offline', goOffline);
  window.addEventListener('online', goOnline);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', syncFromNavigator);
  } else {
    syncFromNavigator();
  }

  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('/sw.js').catch(function () {});
    });
  }
})();
