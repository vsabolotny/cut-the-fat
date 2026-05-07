/* ── Topbar + Settings — shared across all pages ── */

// Tauri detection & global backend URL (consumed by page-specific scripts)
window.IS_TAURI = Boolean(window.__TAURI_INTERNALS__);
window.BACKEND_BASE = '';

window.apiUrl = function(path) {
  return window.BACKEND_BASE ? window.BACKEND_BASE + path : path;
};

// Inject settings drawer + bug modal into the page
(function injectSettingsDrawer() {
  const html = `
    <div id="settings-overlay" class="settings-overlay hidden"></div>
    <aside id="settings-drawer" class="settings-drawer" aria-hidden="true">
      <div class="settings-drawer-header">
        <span class="settings-drawer-title">Einstellungen</span>
        <button id="settings-close" class="icon-btn" title="Schließen">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>
      <div class="settings-drawer-body">
        <section class="settings-section">
          <div class="settings-section-title">Profil</div>
          <div class="settings-field">
            <label class="settings-label">Name</label>
            <input id="s-name" type="text" class="settings-input" placeholder="Paul Wilke">
          </div>
          <div class="settings-field">
            <label class="settings-label">E-Mail</label>
            <input id="s-email" type="email" class="settings-input" placeholder="paul@beispiel.de">
          </div>
        </section>
        <section class="settings-section">
          <div class="settings-section-title">API Keys</div>
          <div class="settings-field">
            <label class="settings-label">Anthropic API Key
              <span id="s-anthropic-pill" class="settings-key-pill off">nicht gesetzt</span>
            </label>
            <div class="settings-input-row">
              <input id="s-anthropic-key" type="password" class="settings-input" placeholder="sk-ant-...">
              <button class="settings-eye-btn" data-target="s-anthropic-key" title="Anzeigen/Verstecken">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
              </button>
            </div>
            <div class="settings-hint">Für KI-Kategorisierung und Sparempfehlungen. Gespeichert in <code>.env</code>.</div>
          </div>
          <div class="settings-field">
            <label class="settings-label">GitHub Token
              <span id="s-github-pill" class="settings-key-pill off">nicht gesetzt</span>
            </label>
            <div class="settings-input-row">
              <input id="s-github-token" type="password" class="settings-input" placeholder="ghp_...">
              <button class="settings-eye-btn" data-target="s-github-token" title="Anzeigen/Verstecken">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
              </button>
            </div>
            <div class="settings-hint">Optional. Für Bug-Reports aus der Desktop-App. Gespeichert in <code>.env</code>.</div>
          </div>
        </section>
        <section class="settings-section">
          <div class="settings-section-title">App</div>
          <div class="settings-field">
            <label class="settings-label">Datenbank</label>
            <div class="settings-info" id="s-db-path">backend/cut_the_fat.db</div>
          </div>
          <div class="settings-field">
            <label class="settings-label">Version</label>
            <div class="settings-info">0.1.0</div>
          </div>
          <div id="s-bug-report-row" class="settings-field" style="display:none">
            <label class="settings-label">Bug melden</label>
            <button id="bug-report-btn" class="settings-action-btn">&#128027; Bug Report erstellen</button>
          </div>
        </section>
      </div>
      <div class="settings-drawer-footer">
        <button id="settings-cancel" class="settings-btn-secondary">Abbrechen</button>
        <button id="settings-save" class="settings-btn-primary">Speichern</button>
      </div>
    </aside>

    <div id="bug-modal" style="display:none; position:fixed; inset:0; background:rgba(0,0,0,0.6); z-index:300; justify-content:center; align-items:center;">
      <div style="background:#1a1d27; border:1px solid #2e3348; border-radius:12px; padding:24px; width:420px; max-width:90vw;">
        <h3 style="margin:0 0 16px; font-size:16px; color:#e4e6f0;">&#128027; Bug melden</h3>
        <input id="bug-title" type="text" placeholder="Kurzbeschreibung..." style="width:100%; padding:8px 12px; margin-bottom:10px; background:#0f1117; border:1px solid #2e3348; border-radius:8px; color:#e4e6f0; font-size:13px; box-sizing:border-box;">
        <textarea id="bug-desc" placeholder="Was ist passiert?" rows="3" style="width:100%; padding:8px 12px; margin-bottom:10px; background:#0f1117; border:1px solid #2e3348; border-radius:8px; color:#e4e6f0; font-size:13px; resize:vertical; box-sizing:border-box;"></textarea>
        <textarea id="bug-steps" placeholder="Schritte zur Reproduktion (optional)" rows="2" style="width:100%; padding:8px 12px; margin-bottom:14px; background:#0f1117; border:1px solid #2e3348; border-radius:8px; color:#e4e6f0; font-size:13px; resize:vertical; box-sizing:border-box;"></textarea>
        <div style="display:flex; gap:8px; justify-content:flex-end;">
          <button id="bug-cancel" style="padding:6px 16px; border-radius:16px; border:1px solid #2e3348; background:#242836; color:#8b8fa8; font-size:12px; cursor:pointer;">Abbrechen</button>
          <button id="bug-submit" style="padding:6px 16px; border-radius:16px; border:1px solid #6366f1; background:rgba(99,102,241,0.15); color:#6366f1; font-size:12px; cursor:pointer;">Senden</button>
        </div>
      </div>
    </div>`;

  const container = document.createElement('div');
  container.innerHTML = html;
  document.body.appendChild(container);
})();

// Wire up settings drawer
(function initSettings() {
  const btn = document.getElementById('settings-btn');
  const drawer = document.getElementById('settings-drawer');
  const overlay = document.getElementById('settings-overlay');
  if (!btn || !drawer) return;

  function openDrawer() {
    drawer.classList.add('open');
    overlay.classList.remove('hidden');
    drawer.setAttribute('aria-hidden', 'false');
    loadSettings();
  }
  function closeDrawer() {
    drawer.classList.remove('open');
    overlay.classList.add('hidden');
    drawer.setAttribute('aria-hidden', 'true');
  }

  btn.addEventListener('click', openDrawer);
  overlay.addEventListener('click', closeDrawer);
  document.getElementById('settings-close').addEventListener('click', closeDrawer);
  document.getElementById('settings-cancel').addEventListener('click', closeDrawer);

  drawer.querySelectorAll('.settings-eye-btn').forEach(eyeBtn => {
    eyeBtn.addEventListener('click', () => {
      const target = document.getElementById(eyeBtn.dataset.target);
      if (target) target.type = target.type === 'password' ? 'text' : 'password';
    });
  });

  const bugRow = document.getElementById('s-bug-report-row');
  if (window.IS_TAURI && bugRow) bugRow.style.display = '';

  async function loadSettings() {
    try {
      const data = await fetch(window.apiUrl('/api/settings')).then(r => r.json());

      const profile = data.profile || {};
      document.getElementById('s-name').value = profile.name || '';
      document.getElementById('s-email').value = profile.email || '';

      const anthPill = document.getElementById('s-anthropic-pill');
      anthPill.textContent = data.anthropic_key_set ? data.anthropic_key_masked : 'nicht gesetzt';
      anthPill.className = 'settings-key-pill ' + (data.anthropic_key_set ? 'on' : 'off');
      document.getElementById('s-anthropic-key').value = '';
      document.getElementById('s-anthropic-key').placeholder = data.anthropic_key_set
        ? data.anthropic_key_masked : 'sk-ant-...';

      const ghPill = document.getElementById('s-github-pill');
      ghPill.textContent = data.github_token_set ? data.github_token_masked : 'nicht gesetzt';
      ghPill.className = 'settings-key-pill ' + (data.github_token_set ? 'on' : 'off');
      document.getElementById('s-github-token').value = '';
      document.getElementById('s-github-token').placeholder = data.github_token_set
        ? data.github_token_masked : 'ghp_...';

      const dbEl = document.getElementById('s-db-path');
      if (dbEl && data.db_path) dbEl.textContent = data.db_path;
    } catch (_) {}
  }

  document.getElementById('settings-save').addEventListener('click', async () => {
    const saveBtn = document.getElementById('settings-save');
    saveBtn.textContent = '…';
    saveBtn.disabled = true;

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
      document.dispatchEvent(new CustomEvent('settingsSaved'));
      closeDrawer();
    } catch (err) {
      alert('Fehler beim Speichern: ' + err.message);
    } finally {
      saveBtn.textContent = 'Speichern';
      saveBtn.disabled = false;
    }
  });
})();

// Bug report modal (submit wired up per-page via 'bugReportSubmit' event)
(function initBugReport() {
  const btn = document.getElementById('bug-report-btn');
  const modal = document.getElementById('bug-modal');
  if (!modal) return;

  function openBugModal() {
    const drawer = document.getElementById('settings-drawer');
    const overlay = document.getElementById('settings-overlay');
    if (drawer) { drawer.classList.remove('open'); drawer.setAttribute('aria-hidden', 'true'); }
    if (overlay) overlay.classList.add('hidden');
    modal.style.display = 'flex';
    document.getElementById('bug-title').focus();
  }

  if (btn) btn.addEventListener('click', openBugModal);

  document.getElementById('bug-cancel').addEventListener('click', () => {
    modal.style.display = 'none';
  });
  modal.addEventListener('click', e => {
    if (e.target === modal) modal.style.display = 'none';
  });

  document.getElementById('bug-submit').addEventListener('click', async () => {
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
