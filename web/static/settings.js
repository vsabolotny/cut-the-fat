/* ── Settings Page ── */

async function loadSettings() {
  try {
    const data = await fetch(window.apiUrl('/api/settings')).then(r => r.json());

    const profile = data.profile || {};
    document.getElementById('s-name').value = profile.name || '';
    document.getElementById('s-email').value = profile.email || '';

    const anthPill = document.getElementById('s-anthropic-pill');
    anthPill.textContent = data.anthropic_key_set ? data.anthropic_key_masked : 'nicht gesetzt';
    anthPill.className = 'settings-key-pill ' + (data.anthropic_key_set ? 'on' : 'off');
    document.getElementById('s-anthropic-key').placeholder = data.anthropic_key_set
      ? data.anthropic_key_masked : 'sk-ant-...';

    const ghPill = document.getElementById('s-github-pill');
    ghPill.textContent = data.github_token_set ? data.github_token_masked : 'nicht gesetzt';
    ghPill.className = 'settings-key-pill ' + (data.github_token_set ? 'on' : 'off');
    document.getElementById('s-github-token').placeholder = data.github_token_set
      ? data.github_token_masked : 'ghp_...';

    const dbEl = document.getElementById('s-db-path');
    if (dbEl && data.db_path) dbEl.textContent = data.db_path;

    const bugRow = document.getElementById('s-bug-report-row');
    if (window.IS_TAURI && bugRow) bugRow.style.display = '';
  } catch (_) {}
}

// Eye-toggle
document.querySelectorAll('.settings-eye-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const t = document.getElementById(btn.dataset.target);
    if (t) t.type = t.type === 'password' ? 'text' : 'password';
  });
});

// Save
document.getElementById('settings-save').addEventListener('click', async () => {
  const btn = document.getElementById('settings-save');
  btn.textContent = '…';
  btn.disabled = true;

  const body = {
    profile: {
      name: document.getElementById('s-name').value.trim(),
      email: document.getElementById('s-email').value.trim(),
    },
  };
  const anthKey = document.getElementById('s-anthropic-key').value.trim();
  if (anthKey) body.anthropic_api_key = anthKey;
  const ghToken = document.getElementById('s-github-token').value.trim();
  if (ghToken) body.github_token = ghToken;

  try {
    await fetch(window.apiUrl('/api/settings'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    document.getElementById('s-anthropic-key').value = '';
    document.getElementById('s-github-token').value = '';
    await loadSettings();
    btn.textContent = '✓ Gespeichert';
    setTimeout(() => { btn.textContent = 'Speichern'; }, 2000);
  } catch (err) {
    alert('Fehler beim Speichern: ' + err.message);
    btn.textContent = 'Speichern';
  } finally {
    btn.disabled = false;
  }
});

// Bug report
document.addEventListener('bugReportSubmit', async (e) => {
  const { title, description, steps } = e.detail;
  try {
    const resp = await fetch(window.apiUrl('/api/bugreport'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, description, steps, chat_log: '' }),
    });
    const result = await resp.json();
    alert(result.url ? `✅ Bug Report erstellt: ${result.url}` : `⚠️ ${result.error}`);
  } catch (err) {
    alert('❌ ' + err.message);
  }
});

// Init — wait for topbar.js to set up BACKEND_BASE in Tauri mode
if (window.IS_TAURI) {
  window.__TAURI_INTERNALS__.invoke('get_backend_port').then(port => {
    window.BACKEND_BASE = `http://localhost:${port}`;
    loadSettings();
  }).catch(() => loadSettings());
} else {
  loadSettings();
}
