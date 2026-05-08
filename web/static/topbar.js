/* ── Topbar — shared globals across all pages ── */

// Tauri detection & global backend URL (consumed by page-specific scripts)
window.IS_TAURI = Boolean(window.__TAURI_INTERNALS__);
window.BACKEND_BASE = '';

window.apiUrl = function(path) {
  return window.BACKEND_BASE ? window.BACKEND_BASE + path : path;
};

// In Tauri mode: resolve the dynamic backend port early so page scripts can use apiUrl() immediately
if (window.IS_TAURI) {
  window.__TAURI_INTERNALS__.invoke('get_backend_port').then(function(port) {
    window.BACKEND_BASE = 'http://localhost:' + port;
  }).catch(function() {});
}

// Bug report modal — only needed on pages that include the #bug-modal element
(function initBugReport() {
  const modal = document.getElementById('bug-modal');
  if (!modal) return;

  const btn = document.getElementById('bug-report-btn');

  function openBugModal() {
    modal.style.display = 'flex';
    const titleEl = document.getElementById('bug-title');
    if (titleEl) titleEl.focus();
  }

  if (btn) btn.addEventListener('click', openBugModal);

  const cancelBtn = document.getElementById('bug-cancel');
  if (cancelBtn) cancelBtn.addEventListener('click', () => { modal.style.display = 'none'; });

  modal.addEventListener('click', e => {
    if (e.target === modal) modal.style.display = 'none';
  });

  const submitBtn = document.getElementById('bug-submit');
  if (submitBtn) submitBtn.addEventListener('click', () => {
    const title = document.getElementById('bug-title').value.trim();
    const desc = document.getElementById('bug-desc').value.trim();
    const steps = document.getElementById('bug-steps').value.trim();
    if (!title && !desc) return;

    modal.style.display = 'none';
    document.dispatchEvent(new CustomEvent('bugReportSubmit', {
      detail: { title, description: desc, steps }
    }));

    document.getElementById('bug-title').value = '';
    document.getElementById('bug-desc').value = '';
    document.getElementById('bug-steps').value = '';
  });
})();
