/* ── Login-Seite (CAT-28) ──
 * Zwei Modi im selben Formular: "Passwort festlegen" beim Erststart,
 * "Anmelden" danach. Welcher gilt, sagt /api/auth/status.
 */
(function () {
  const form = document.getElementById('login-card');
  const lead = document.getElementById('login-lead');
  const passwordInput = document.getElementById('login-password');
  const confirmField = document.getElementById('login-confirm-field');
  const confirmInput = document.getElementById('login-confirm');
  const errorBox = document.getElementById('login-error');
  const submitBtn = document.getElementById('login-submit');

  let setupRequired = false;

  function showError(message) {
    errorBox.textContent = message;
    errorBox.classList.remove('hidden');
  }

  function clearError() {
    errorBox.textContent = '';
    errorBox.classList.add('hidden');
  }

  function applyMode() {
    if (setupRequired) {
      lead.textContent = 'Lege ein Passwort fest, um deine Finanzdaten zu schützen.';
      submitBtn.textContent = 'Passwort festlegen';
      confirmField.classList.remove('hidden');
      passwordInput.setAttribute('autocomplete', 'new-password');
    } else {
      lead.textContent = 'Melde dich an, um fortzufahren.';
      submitBtn.textContent = 'Anmelden';
      confirmField.classList.add('hidden');
      passwordInput.setAttribute('autocomplete', 'current-password');
    }
    passwordInput.disabled = false;
    submitBtn.disabled = false;
    passwordInput.focus();
  }

  async function loadStatus() {
    try {
      const response = await window.apiFetch('/api/auth/status');
      const data = await response.json();
      setupRequired = Boolean(data.setup_required);
    } catch (e) {
      // Backend nicht erreichbar: Login-Formular anzeigen, der Submit meldet
      // den Fehler dann konkret.
      setupRequired = false;
    }
    applyMode();
  }

  async function submit(event) {
    event.preventDefault();
    clearError();

    const password = passwordInput.value;
    if (setupRequired && password !== confirmInput.value) {
      showError('Die Passwörter stimmen nicht überein.');
      return;
    }

    submitBtn.disabled = true;
    const endpoint = setupRequired ? '/api/auth/setup' : '/api/auth/login';

    let response;
    try {
      response = await window.apiFetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: password }),
      });
    } catch (e) {
      showError('Backend nicht erreichbar.');
      submitBtn.disabled = false;
      return;
    }

    const data = await response.json().catch(function () { return {}; });

    if (!response.ok) {
      showError(data.error || 'Anmeldung fehlgeschlagen.');
      submitBtn.disabled = false;
      // Ein 409 heißt: Zwischenzeitlich wurde ein Passwort gesetzt. Formular
      // umschalten statt den Nutzer im Setup-Modus hängen zu lassen.
      if (response.status === 409) {
        setupRequired = false;
        applyMode();
      }
      return;
    }

    window.setSessionToken(data.token);
    location.href = window.APP_URL;
  }

  if (new URLSearchParams(location.search).get('expired')) {
    showError('Sitzung abgelaufen, bitte erneut anmelden.');
  }

  form.addEventListener('submit', submit);
  loadStatus();
})();
