/* ── Settings Page ── */

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

async function loadSettings() {
  try {
    const data = await (await window.apiFetch('/api/settings')).json();

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

    const versionEl = document.getElementById('s-version');
    if (versionEl) versionEl.textContent = data.version || '–';

    const bugRow = document.getElementById('s-bug-report-row');
    if (window.IS_TAURI && bugRow) bugRow.classList.remove('hidden');
  } catch (_) {}
}

// Eye-toggle
document.querySelectorAll('.settings-eye-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const t = document.getElementById(btn.dataset.target);
    if (t) t.type = t.type === 'password' ? 'text' : 'password';
  });
});

// Cancel button (replaces inline onclick=history.back())
const cancelBtn = document.getElementById('settings-cancel');
if (cancelBtn) cancelBtn.addEventListener('click', () => history.back());

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
    await window.apiFetch('/api/settings', {
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
function safeIssueUrl(url) {
  if (typeof url !== 'string') return null;
  try {
    const u = new URL(url);
    if (u.protocol === 'https:' && u.hostname === 'github.com') return u.href;
  } catch (_) {}
  return null;
}

document.addEventListener('bugReportSubmit', async (e) => {
  const { title, description, steps, includeChatLog } = e.detail;
  try {
    const resp = await window.apiFetch('/api/bugreport', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title,
        description,
        steps,
        include_chat_log: !!includeChatLog,
        chat_log: '',
      }),
    });
    const result = await resp.json();
    const safeUrl = safeIssueUrl(result.url);
    if (safeUrl) {
      alert('✅ Bug Report erstellt: ' + safeUrl);
    } else if (result.url) {
      alert('✅ Bug Report erstellt: ' + result.url);
    } else {
      alert('⚠️ ' + (result.error || 'Unbekannter Fehler'));
    }
  } catch (err) {
    alert('❌ ' + err.message);
  }
});

// Init — single source of truth lives in topbar.js (window.backendReady).
(async () => {
  await window.backendReady;
  loadSettings();
})();
