/* ── Cut the Fat — Split-View (WebSocket-Backend) ── */

const chatMessages = document.getElementById('chat-messages');
const form = document.getElementById('input-form');
const input = document.getElementById('msg-input');
const fileInput = document.getElementById('file-input');
const dropZone = document.getElementById('drop-zone');
const contentHeader = document.getElementById('content-header');
const contentArea = document.getElementById('content-area');
const primary = document.getElementById('content-primary');
const secondary = document.getElementById('content-secondary');
const contentActions = document.getElementById('content-actions');
const welcome = document.getElementById('welcome');

// ── Helpers ──

function fmtEur(n) {
  return n.toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' \u20AC';
}

function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

function scrollChat() {
  requestAnimationFrame(() => chatMessages.scrollTop = chatMessages.scrollHeight);
}

function scrollContent() {
  requestAnimationFrame(() => contentArea.scrollTop = 0);
}

const COLORS = [
  '#6366f1', '#22c55e', '#f97316', '#3b82f6', '#a855f7',
  '#ec4899', '#eab308', '#14b8a6', '#06b6d4', '#8b5cf6', '#64748b',
];

let chartInstances = [];
let chartCounter = 0;

function destroyCharts() {
  chartInstances.forEach(c => c.destroy());
  chartInstances = [];
}

// ── WebSocket ──

let ws = null;
let reconnectTimer = null;
let heartbeatTimer = null;

function connectWS() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${proto}//${location.host}/ws/chat`);

  ws.onopen = () => {
    console.log('WS connected');
    // Start heartbeat
    heartbeatTimer = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'ping' }));
    }, 30000);
  };

  ws.onmessage = (e) => {
    const data = JSON.parse(e.data);
    handleServerMessage(data);
  };

  ws.onclose = () => {
    console.log('WS closed, reconnecting...');
    clearInterval(heartbeatTimer);
    reconnectTimer = setTimeout(connectWS, 2000);
  };

  ws.onerror = () => ws.close();
}

function sendText(text) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    const context = {
      month: document.getElementById('app').dataset.currentMonth || null,
      intent: document.getElementById('app').dataset.lastIntent || null,
    };
    ws.send(JSON.stringify({ type: 'text', content: text, context }));
  }
}

function sendAction(action, payload) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'action', action, payload }));
  }
}

// ── Chat (left panel) ──

function addUser(text) {
  const div = document.createElement('div');
  div.className = 'msg user';
  div.innerHTML = `<div class="msg-bubble">${esc(text)}</div>`;
  chatMessages.appendChild(div);
  scrollChat();
}

function addBot(html) {
  removeProgress();
  const div = document.createElement('div');
  div.className = 'msg bot';
  // Convert **bold** to <strong>
  const formatted = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  div.innerHTML = `<div class="msg-bubble">${formatted}</div>`;
  chatMessages.appendChild(div);
  scrollChat();
  return div;
}

function addBotActions(buttons) {
  const div = document.createElement('div');
  div.className = 'msg bot';
  let h = `<div class="msg-bubble"><div class="chat-actions">`;
  buttons.forEach((b, i) => {
    h += `<button class="action-btn" data-idx="${i}">${esc(b.label)}</button>`;
  });
  h += `</div></div>`;
  div.innerHTML = h;
  chatMessages.appendChild(div);
  scrollChat();
  div.querySelectorAll('.action-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const b = buttons[btn.dataset.idx];
      if (b.action === 'send' && b.payload && b.payload.text) {
        handleUserInput(b.payload.text);
      }
    });
  });
  return div;
}

let progressEl = null;
function showProgress(text) {
  removeProgress();
  const div = document.createElement('div');
  div.className = 'msg bot';
  div.innerHTML = `<div class="msg-bubble"><div class="msg-progress"><div class="spinner"></div><span>${esc(text)}</span></div></div>`;
  chatMessages.appendChild(div);
  scrollChat();
  progressEl = div;
}

function removeProgress() {
  if (progressEl && progressEl.parentNode) {
    progressEl.parentNode.removeChild(progressEl);
    progressEl = null;
  }
}

// ── Content (right panel) ──

function clearContent() {
  destroyCharts();
  welcome.classList.add('hidden');
  contentHeader.classList.add('hidden');
  contentHeader.innerHTML = '';
  primary.innerHTML = '';
  primary.classList.add('hidden');
  secondary.innerHTML = '';
  secondary.classList.add('hidden');
  contentActions.innerHTML = '';
  contentActions.classList.add('hidden');
}

function showSection(el) { el.classList.remove('hidden'); }

function renderTable(container, msg) {
  showSection(container);
  const div = document.createElement('div');
  div.className = 'table-card';
  let h = '';
  if (msg.title) h += `<div class="table-title">${esc(msg.title)}</div>`;
  h += `<div class="table-scroll"><table class="data-table"><thead><tr>`;
  msg.columns.forEach(c => h += `<th>${esc(c)}</th>`);
  h += `</tr></thead><tbody>`;
  msg.rows.forEach(r => {
    h += '<tr>';
    r.forEach((cell, ci) => {
      const col = msg.columns[ci] || '';
      const isNum = typeof cell === 'number';
      if (isNum && (col.includes('Betrag') || col === 'Ausgaben' || col === 'Einnahmen' || col === 'Bilanz' || col === 'Δ')) {
        const cls = col === 'Δ' ? (cell > 0 ? 'num delta-up' : cell < 0 ? 'num delta-down' : 'num') :
                    col === 'Bilanz' ? 'num' : 'num';
        const prefix = col === 'Δ' && cell > 0 ? '+' : '';
        h += `<td class="${cls}">${prefix}${fmtEur(cell)}</td>`;
      } else if (isNum && col.includes('Anteil')) {
        const barW = Math.round(cell / 40 * 100);
        const color = COLORS[msg.rows.indexOf(r) % COLORS.length];
        h += `<td><div class="bar-cell"><span class="num">${cell.toFixed(1)}%</span><div class="bar-track"><div class="bar-fill" style="width:${barW}%;background:${color}"></div></div></div></td>`;
      } else {
        h += `<td>${isNum ? fmtEur(cell) : esc(String(cell))}</td>`;
      }
    });
    h += '</tr>';
  });
  h += `</tbody></table></div>`;
  div.innerHTML = h;
  container.appendChild(div);
}

function renderChart(container, msg) {
  showSection(container);
  const div = document.createElement('div');
  div.className = 'chart-card';
  const id = 'chart-' + (++chartCounter);
  div.innerHTML = `
    ${msg.title ? `<div class="chart-title">${esc(msg.title)}</div>` : ''}
    <canvas id="${id}"></canvas>`;
  container.appendChild(div);

  requestAnimationFrame(() => {
    const ctx = document.getElementById(id);
    const chartType = msg.chart_type;
    const datasets = msg.data.datasets.map((ds, i) => {
      const base = { ...ds };
      if (chartType === 'doughnut' || chartType === 'pie') {
        base.backgroundColor = base.backgroundColor || COLORS;
        base.borderWidth = base.borderWidth ?? 0;
      } else if (chartType === 'bar') {
        if (i === 0) { base.backgroundColor = base.backgroundColor || '#6366f1'; base.borderRadius = 4; }
        if (i === 1) { base.backgroundColor = base.backgroundColor || 'rgba(34,197,94,0.3)'; base.borderColor = '#22c55e'; base.borderWidth = 1; base.borderRadius = 4; }
      } else if (chartType === 'line') {
        base.borderColor = base.borderColor || '#f97316';
        base.backgroundColor = base.backgroundColor || 'rgba(249,115,22,0.1)';
        base.fill = true;
        base.tension = 0.3;
      }
      return base;
    });

    const instance = new Chart(ctx, {
      type: chartType,
      data: { labels: msg.data.labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
          legend: { labels: { color: '#8b8fa8', font: { size: 11 } },
                    position: chartType === 'doughnut' ? 'right' : 'top' },
        },
        ...(chartType === 'doughnut' ? { cutout: '60%' } : {}),
        scales: chartType === 'pie' || chartType === 'doughnut' ? {} : {
          x: { ticks: { color: '#8b8fa8' }, grid: { color: '#2e3348' } },
          y: { ticks: { color: '#8b8fa8' }, grid: { color: '#2e3348' } },
        },
      },
    });
    chartInstances.push(instance);
  });
}

function renderInsight(container, msg) {
  showSection(container);
  const icons = { warning: '\u26A0\uFE0F', info: '\u2139\uFE0F', success: '\u2705' };
  const type = msg.insight_type || 'info';
  const div = document.createElement('div');
  div.className = `insight-card ${type}`;
  const formatted = msg.text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  div.innerHTML = `<span class="insight-icon">${icons[type] || ''}</span>${formatted}`;
  container.appendChild(div);
}

function renderLearnTable(msg) {
  clearContent();
  contentHeader.innerHTML = `Kategorien lernen — ${msg.total} Händler`;
  contentHeader.classList.remove('hidden');
  showSection(primary);

  const merchants = msg.merchants;
  const categories = msg.categories || [];
  const choices = {};

  // Status bar
  const statusBar = document.createElement('div');
  statusBar.className = 'learn-status';
  primary.appendChild(statusBar);

  function updateStatus() {
    const done = Object.values(choices).filter(v => v).length;
    statusBar.innerHTML = `<span>${done} / ${merchants.length} kategorisiert</span>`;
    if (saveBtn) {
      saveBtn.disabled = done === 0;
      saveBtn.style.opacity = done === 0 ? '0.4' : '1';
    }
  }

  // Table
  const tableCard = document.createElement('div');
  tableCard.className = 'table-card';
  let html = `<div class="table-scroll"><table class="data-table learn-table">
    <thead><tr><th>#</th><th>Händler</th><th>Txn</th><th>KI-Vorschlag</th><th>Gewählt</th><th></th></tr></thead><tbody>`;
  merchants.forEach((m, i) => {
    html += `<tr data-merchant="${esc(m.merchant)}" data-idx="${i}">
      <td class="num">${i + 1}</td>
      <td>${esc(m.display)}</td>
      <td class="num">${m.count}</td>
      <td><span class="ki-suggestion" data-idx="${i}">${esc(m.suggestion)}</span></td>
      <td class="chosen-cell">\u2014</td>
      <td><button class="action-btn row-edit-btn" data-idx="${i}">Ändern</button></td>
    </tr>`;
  });
  html += `</tbody></table></div>`;
  tableCard.innerHTML = html;
  primary.appendChild(tableCard);

  // Click KI-Vorschlag → accept directly
  tableCard.querySelectorAll('.ki-suggestion').forEach(el => {
    el.style.cursor = 'pointer';
    el.title = 'Klick = übernehmen';
    el.addEventListener('click', () => {
      const idx = parseInt(el.dataset.idx);
      const m = merchants[idx];
      choices[m.merchant] = m.suggestion;
      const tr = tableCard.querySelector(`tr[data-idx="${idx}"]`);
      tr.querySelector('.chosen-cell').innerHTML = `<span class="chosen-tag">${esc(m.suggestion)}</span>`;
      tr.classList.add('row-done');
      updateStatus();
      addBot(`\u2705 ${esc(m.display)} \u2192 ${esc(m.suggestion)}`);
    });
  });

  // Ändern button → modal
  tableCard.querySelectorAll('.row-edit-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const idx = parseInt(btn.dataset.idx);
      openCategoryModal(merchants[idx], categories, choices, tableCard, updateStatus);
    });
  });

  // Action buttons
  showSection(contentActions);
  const btnRow = document.createElement('div');
  btnRow.className = 'panel-actions';

  const acceptAllBtn = document.createElement('button');
  acceptAllBtn.className = 'action-btn';
  acceptAllBtn.textContent = 'Alle KI-Vorschläge übernehmen';
  acceptAllBtn.addEventListener('click', () => {
    merchants.forEach((m, i) => {
      if (!choices[m.merchant]) {
        choices[m.merchant] = m.suggestion;
        const tr = tableCard.querySelector(`tr[data-idx="${i}"]`);
        tr.querySelector('.chosen-cell').innerHTML = `<span class="chosen-tag">${esc(m.suggestion)}</span>`;
        tr.classList.add('row-done');
      }
    });
    updateStatus();
    acceptAllBtn.classList.add('selected');
    acceptAllBtn.textContent = '\u2713 Alle übernommen';
    addBot('\u2705 Alle KI-Vorschläge übernommen.');
  });

  const saveBtn = document.createElement('button');
  saveBtn.className = 'action-btn';
  saveBtn.textContent = 'Speichern';
  saveBtn.style.borderColor = 'var(--green)';
  saveBtn.style.color = 'var(--green)';
  saveBtn.disabled = true;
  saveBtn.style.opacity = '0.4';
  saveBtn.addEventListener('click', () => {
    const rules = Object.entries(choices)
      .filter(([_, v]) => v)
      .map(([merchant, category]) => ({ merchant, category }));
    sendAction('save_rules', { rules });
    saveBtn.classList.add('selected');
    saveBtn.textContent = '\u2713 Gespeichert';
  });

  btnRow.appendChild(acceptAllBtn);
  btnRow.appendChild(saveBtn);
  contentActions.appendChild(btnRow);

  updateStatus();
  scrollContent();
}

function openCategoryModal(merchant, categories, choices, tableCard, updateStatus) {
  const existing = document.getElementById('cat-modal');
  if (existing) existing.remove();

  const modal = document.createElement('div');
  modal.id = 'cat-modal';
  modal.className = 'cat-modal-overlay';
  const current = choices[merchant.merchant] || merchant.suggestion;
  const opts = categories.map(c =>
    `<option value="${esc(c)}" ${c === current ? 'selected' : ''}>${esc(c)}</option>`
  ).join('');
  modal.innerHTML = `
    <div class="cat-modal">
      <div class="cat-modal-title">${esc(merchant.display)}</div>
      <div class="cat-modal-subtitle">${merchant.count} Transaktionen</div>
      <select class="cat-select">${opts}</select>
      <div class="cat-modal-actions">
        <button class="action-btn cat-modal-cancel">Abbrechen</button>
        <button class="action-btn cat-modal-ok" style="border-color:var(--accent);color:var(--accent);">Übernehmen</button>
      </div>
    </div>`;
  document.body.appendChild(modal);

  modal.querySelector('.cat-modal-cancel').addEventListener('click', () => modal.remove());
  modal.addEventListener('click', e => { if (e.target === modal) modal.remove(); });
  modal.querySelector('.cat-modal-ok').addEventListener('click', () => {
    const selected = modal.querySelector('.cat-select').value;
    choices[merchant.merchant] = selected;
    const idx = merchant.idx;
    const tr = tableCard.querySelector(`tr[data-idx="${idx}"]`);
    tr.querySelector('.chosen-cell').innerHTML = `<span class="chosen-tag">${esc(selected)}</span>`;
    tr.classList.add('row-done');
    updateStatus();
    addBot(`\u2705 ${esc(merchant.display)} \u2192 ${esc(selected)}`);
    modal.remove();
  });

  modal.querySelector('.cat-select').focus();
}

function renderReportPreview(msg) {
  showSection(primary);
  const div = document.createElement('div');
  div.className = 'report-preview';
  div.innerHTML = `<pre>${esc(msg.content)}</pre>`;
  primary.appendChild(div);
}

// ── Server message dispatch ──

let contentCleared = false;

function handleServerMessage(data) {
  switch (data.type) {
    case 'pong':
      break;

    case 'progress':
      showProgress(data.message);
      break;

    case 'text':
      addBot(data.content);
      break;

    case 'content_header':
      if (!contentCleared) { clearContent(); contentCleared = true; }
      contentHeader.innerHTML = esc(data.text);
      contentHeader.classList.remove('hidden');
      break;

    case 'chart':
      if (!contentCleared) { clearContent(); contentCleared = true; }
      renderChart(primary, data);
      break;

    case 'table':
      if (!contentCleared) { clearContent(); contentCleared = true; }
      renderTable(secondary.innerHTML ? secondary : primary, data);
      break;

    case 'insight':
      if (!contentCleared) { clearContent(); contentCleared = true; }
      renderInsight(primary, data);
      break;

    case 'learn_table':
      contentCleared = true;
      renderLearnTable(data);
      break;

    case 'report_preview':
      if (!contentCleared) { clearContent(); contentCleared = true; }
      renderReportPreview(data);
      break;

    case 'actions':
      addBotActions(data.buttons || []);
      break;

    case 'set_context':
      if (data.month) document.getElementById('app').dataset.currentMonth = data.month;
      if (data.intent) document.getElementById('app').dataset.lastIntent = data.intent;
      contentCleared = false;
      scrollContent();
      break;

    case 'rule_applied':
    case 'all_rules_applied':
    case 'learn_saved':
      // Already handled via text messages
      break;

    default:
      console.log('Unknown message type:', data.type, data);
  }
}

// ── User input ──

function handleUserInput(text) {
  addUser(text);
  input.value = '';
  contentCleared = false;
  sendText(text);
}

// ── Events ──

form.addEventListener('submit', e => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  handleUserInput(text);
});

// Quick cards on welcome screen
welcome.addEventListener('click', e => {
  const card = e.target.closest('.quick-card');
  if (!card) return;
  handleUserInput(card.dataset.q);
});

// File upload
fileInput.addEventListener('change', async () => {
  if (!fileInput.files.length) return;
  const file = fileInput.files[0];
  fileInput.value = '';

  addUser(`📎 ${file.name}`);
  showProgress('Verarbeite Kontoauszug...');

  const formData = new FormData();
  formData.append('file', file);

  try {
    const resp = await fetch('/api/upload', { method: 'POST', body: formData });
    const result = await resp.json();
    removeProgress();

    if (result.error) {
      addBot(`❌ ${esc(result.error)}`);
    } else {
      addBot(`✅ **${result.imported}** Transaktionen importiert, **${result.skipped}** Duplikate übersprungen.`);
      addBotActions([
        { label: '🏷 Kategorien prüfen', action: 'send', payload: { text: 'Unkategorisierte Händler' } },
        { label: '📊 Ausgaben anzeigen', action: 'send', payload: { text: 'Zeig mir meine Ausgaben' } },
      ]);
    }
  } catch (err) {
    removeProgress();
    addBot(`❌ Upload fehlgeschlagen: ${esc(err.message)}`);
  }
});

// Drag & drop
document.addEventListener('dragenter', e => { e.preventDefault(); dropZone.classList.remove('hidden'); });
dropZone.addEventListener('dragleave', e => { e.preventDefault(); dropZone.classList.add('hidden'); });
dropZone.addEventListener('dragover', e => e.preventDefault());
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.add('hidden');
  if (e.dataTransfer.files.length) {
    const dt = new DataTransfer();
    dt.items.add(e.dataTransfer.files[0]);
    fileInput.files = dt.files;
    fileInput.dispatchEvent(new Event('change'));
  }
});

// ── Init ──
connectWS();
