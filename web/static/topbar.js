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

// Wrapper that injects the X-CTF-Token header. Use this for every /api/* call
// instead of fetch() so the Tauri sidecar auth gate is satisfied.
window.apiFetch = async function (path, opts) {
  await window.backendReady;
  opts = opts || {};
  const headers = Object.assign({}, opts.headers || {});
  if (window.AUTH_TOKEN) {
    headers['X-CTF-Token'] = window.AUTH_TOKEN;
  }
  return fetch(window.apiUrl(path), Object.assign({}, opts, { headers: headers }));
};

// WebSocket URL builder — appends ?token=… in Tauri mode.
window.wsUrl = function (path) {
  if (window.BACKEND_BASE) {
    const wsBase = window.BACKEND_BASE.replace(/^http/, 'ws');
    const query = window.AUTH_TOKEN ? '?token=' + encodeURIComponent(window.AUTH_TOKEN) : '';
    return wsBase + path + query;
  }
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  return proto + '//' + location.host + path;
};

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
