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
      'padding:10px 16px', 'text-align:center',
      'font:600 13px/1.4 Inter,system-ui,sans-serif',
      'background:#9a3412', 'color:#fff7ed', 'display:none',
      'box-shadow:0 4px 16px rgba(0,0,0,.18)'
    ].join(';');
    el.textContent = 'Offline mode — same dashboard, data from this device. Changes will sync when you are back online.';
    document.body.appendChild(el);
    return el;
  }

  function setOfflineUI(offline) {
    try { localStorage.setItem('estacle_net', offline ? 'offline' : 'online'); } catch (e) {}
    var banner = ensureBanner();
    if (offline) {
      banner.style.display = 'block';
      if (document.body) document.body.style.paddingTop = '40px';
      document.documentElement.classList.add('estacle-offline');
    } else {
      banner.style.display = 'none';
      if (document.body) document.body.style.paddingTop = '';
      document.documentElement.classList.remove('estacle-offline');
    }
    try {
      window.dispatchEvent(new CustomEvent('estacle:connection', { detail: { offline: offline } }));
    } catch (e) {}
  }

  function goOffline() { setOfflineUI(true); }
  function goOnline() {
    setOfflineUI(false);
    try {
      if (window.API && API.pushPending) API.pushPending().then(function () {
        if (API.snapshot) return API.snapshot();
      }).catch(function () {});
    } catch (e) {}
  }

  function sync() {
    if (typeof navigator.onLine === 'boolean' && !navigator.onLine) goOffline();
    else goOnline();
  }

  window.addEventListener('offline', goOffline);
  window.addEventListener('online', goOnline);

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', sync);
  else sync();

  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('/sw.js').catch(function () {});
    });
  }
})();
