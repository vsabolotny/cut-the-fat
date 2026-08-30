/* ── Topbar — shared globals across all pages ── */

// Tauri detection + globals consumed by page-specific scripts.
window.IS_TAURI = Boolean(window.__TAURI_INTERNALS__);
window.BACKEND_BASE = '';
window.AUTH_TOKEN = '';

// Promise that resolves once the backend port (and auth token) are known.
// Standalone web mode resolves immediately.
window.backendReady = (function () {
  if (!window.IS_TAURI) return Promise.resolve();
  return window.__TAURI_INTERNALS__.invoke('get_backend_info').then(function (info) {
    window.BACKEND_BASE = 'http://localhost:' + info.port;
    window.AUTH_TOKEN = info.token || '';
  }).catch(function (err) {
    console.error('Backend info IPC failed:', err);
  });
})();

window.apiUrl = function (path) {
  return window.BACKEND_BASE ? window.BACKEND_BASE + path : path;
};

/* ── User session (CAT-28) ──
 * Zweite, vom Sidecar-Token unabhängige Ebene: der Login-Token aus
 * /api/auth/login. Liegt in localStorage, damit ein Reload eingeloggt bleibt.
 */
window.SESSION_STORAGE_KEY = 'ctf_session';

window.getSessionToken = function () {
  try {
    return localStorage.getItem(window.SESSION_STORAGE_KEY) || '';
  } catch (e) {
    // localStorage kann im WebView blockiert sein — dann ist die Session
    // eben nur so lang wie die Seite lebt.
    return window.__sessionFallback || '';
  }
};

window.setSessionToken = function (token) {
  window.__sessionFallback = token;
  try {
    localStorage.setItem(window.SESSION_STORAGE_KEY, token);
  } catch (e) { /* siehe getSessionToken */ }
};

window.clearSessionToken = function () {
  window.__sessionFallback = '';
  try {
    localStorage.removeItem(window.SESSION_STORAGE_KEY);
  } catch (e) { /* siehe getSessionToken */ }
};

// Wrapper that injects the X-CTF-Token header (Tauri sidecar gate) and the
// Authorization bearer token (user login). Use this for every /api/* call
// instead of fetch() so both gates are satisfied.
window.apiFetch = async function (path, opts) {
  await window.backendReady;
  opts = opts || {};
  const headers = Object.assign({}, opts.headers || {});
  if (window.AUTH_TOKEN) {
    headers['X-CTF-Token'] = window.AUTH_TOKEN;
  }
  const session = window.getSessionToken();
  if (session) {
    headers['Authorization'] = 'Bearer ' + session;
  }
  const response = await fetch(
    window.apiUrl(path), Object.assign({}, opts, { headers: headers })
  );
  // Abgelaufene oder verworfene Session: Token wegwerfen und zurück zum Login.
  // Nicht auf der Login-Seite (der Redirect drehte sich im Kreis) und nicht
  // während eines gewollten Logouts — dort laufen noch Requests der alten
  // Seite, die naturgemäß 401 bekommen und sonst "Sitzung abgelaufen" melden
  // würden, obwohl der Nutzer selbst geklickt hat.
  if (response.status === 401 && !window.__loggingOut
      && !location.pathname.startsWith('/login')) {
    window.clearSessionToken();
    location.href = window.LOGIN_URL + '?expired=1';
  }
  return response;
};

// WebSocket URL builder — appends ?token=… in Tauri mode and always the
// user session token.
window.wsUrl = function (path) {
  const params = new URLSearchParams();
  const session = window.getSessionToken();
  if (session) params.set('session', session);

  if (window.BACKEND_BASE) {
    const wsBase = window.BACKEND_BASE.replace(/^http/, 'ws');
    if (window.AUTH_TOKEN) params.set('token', window.AUTH_TOKEN);
    return wsBase + path + '?' + params.toString();
  }
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  return proto + '//' + location.host + path + '?' + params.toString();
};

// Seite, auf die ein Logout oder eine fehlende Session führt. In Tauri sind
// die Seiten gebündelte Dateien (tauri://localhost/index.html), es gibt dort
// keine Server-Route "/login".
window.LOGIN_URL = window.IS_TAURI ? 'login.html' : '/login';
window.APP_URL = window.IS_TAURI ? 'index.html' : '/';

/* Client-Gate für den Desktop-Modus.
 * In Tauri liefert nicht der Sidecar die Seiten aus, sondern der WebView aus
 * dem Bundle — die LoginRequiredMiddleware sieht diese Aufrufe also nie. Ohne
 * diesen Check wäre die Desktop-App komplett ungeschützt.
 * Im Browser bleibt der Server die Instanz, die entscheidet.
 */
(function guardTauriPages() {
  if (!window.IS_TAURI) return;
  if (location.pathname.indexOf('login') !== -1) return;
  if (window.getSessionToken()) return;
  location.href = window.LOGIN_URL;
})();

// Logout-Button in die Topbar hängen — nur auf Seiten, die eine haben.
(function initLogout() {
  const slot = document.getElementById('topbar-right');
  if (!slot) return;

  const btn = document.createElement('button');
  btn.id = 'logout-btn';
  btn.className = 'topbar-nav-link';
  btn.type = 'button';
  btn.textContent = 'Abmelden';
  btn.addEventListener('click', function () {
    window.__loggingOut = true;
    // Erst den Server informieren, dann das Token verwerfen — apiFetch liest
    // das Token asynchron, ein vorheriges clear() würde den Aufruf ohne
    // Authorization-Header losschicken.
    window.apiFetch('/api/auth/logout', { method: 'POST' })
      .catch(function () { /* Logout ist serverseitig ein No-op */ })
      .then(function () {
        window.clearSessionToken();
        location.href = window.LOGIN_URL;
      });
  });
  slot.appendChild(btn);
})();

// Bug report modal — only wires up on pages that include the #bug-modal element.
(function initBugReport() {
  const modal = document.getElementById('bug-modal');
  if (!modal) return;

  const openBtn = document.getElementById('bug-report-btn');
  function openBugModal() {
    modal.classList.remove('hidden');
    const titleEl = document.getElementById('bug-title');
    if (titleEl) titleEl.focus();
  }
  function closeBugModal() {
    modal.classList.add('hidden');
  }

  if (openBtn) openBtn.addEventListener('click', openBugModal);

  const cancelBtn = document.getElementById('bug-cancel');
  if (cancelBtn) cancelBtn.addEventListener('click', closeBugModal);

  modal.addEventListener('click', function (e) {
    if (e.target === modal) closeBugModal();
  });

  const submitBtn = document.getElementById('bug-submit');
  if (submitBtn) submitBtn.addEventListener('click', function () {
    const title = document.getElementById('bug-title').value.trim();
    const desc = document.getElementById('bug-desc').value.trim();
    const steps = document.getElementById('bug-steps').value.trim();
    const includeLog = document.getElementById('bug-include-log');
    const includeChatLog = includeLog ? includeLog.checked : false;

    if (!title && !desc) return;

    closeBugModal();
    document.dispatchEvent(new CustomEvent('bugReportSubmit', {
      detail: { title: title, description: desc, steps: steps, includeChatLog: includeChatLog },
    }));

    document.getElementById('bug-title').value = '';
    document.getElementById('bug-desc').value = '';
    document.getElementById('bug-steps').value = '';
    if (includeLog) includeLog.checked = false;
  });
})();
