/* ── Transaktionen — Filter + Tabelle + Kategorie-Edit ── */

const tbody = document.getElementById('txn-body');
const loading = document.getElementById('txn-loading');
const empty = document.getElementById('txn-empty');
const pagination = document.getElementById('pagination');
const statCount = document.getElementById('stat-count');
const statDebit = document.getElementById('stat-debit');
const statCredit = document.getElementById('stat-credit');
const dateFrom = document.getElementById('date-from');
const dateTo = document.getElementById('date-to');
const filterCategory = document.getElementById('filter-category');
const filterType = document.getElementById('filter-type');
const filterMerchant = document.getElementById('filter-merchant');
const modal = document.getElementById('cat-modal');
const modalMerchant = document.getElementById('modal-merchant');
const modalInfo = document.getElementById('modal-info');
const modalSelect = document.getElementById('modal-select');
const modalApplyAll = document.getElementById('modal-apply-all');
const modalCancel = document.getElementById('modal-cancel');
const modalOk = document.getElementById('modal-ok');

const PAGE_SIZE = 50;
let currentOffset = 0;
let allCategories = [];
let debounceTimer = null;

// ── Helpers ──

function fmtEur(n) {
  return n.toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' \u20AC';
}

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function fmtDate(dateStr) {
  const d = new Date(dateStr);
  return d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

// ── Quick date ranges ──

function getDateRange(range) {
  const now = new Date();
  const y = now.getFullYear();
  const m = now.getMonth(); // 0-based
  const d = now.getDate();

  switch (range) {
    case 'this-month':
      return { from: `${y}-${String(m + 1).padStart(2, '0')}-01`, to: toISO(now) };
    case 'last-month': {
      const ly = m === 0 ? y - 1 : y;
      const lm = m === 0 ? 12 : m;
      const lastDay = new Date(ly, lm, 0).getDate();
      return { from: `${ly}-${String(lm).padStart(2, '0')}-01`, to: `${ly}-${String(lm).padStart(2, '0')}-${lastDay}` };
    }
    case 'last-quarter': {
      const qStart = new Date(y, m - 3, 1);
      const qEnd = new Date(y, m, 0);
      return { from: toISO(qStart), to: toISO(qEnd) };
    }
    case 'this-year':
      return { from: `${y}-01-01`, to: toISO(now) };
    case 'all':
      return { from: '', to: '' };
    default:
      return { from: '', to: '' };
  }
}

function toISO(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

// ── Load categories ──

async function loadCategories() {
  try {
    const resp = await fetch('/api/categories');
    allCategories = await resp.json();
    filterCategory.innerHTML = '<option value="Alle">Alle Kategorien</option>';
    allCategories.forEach(c => {
      filterCategory.innerHTML += `<option value="${esc(c)}">${esc(c)}</option>`;
    });
  } catch (e) {
    console.error('Failed to load categories', e);
  }
}

// ── Load transactions ──

async function loadTransactions() {
  loading.classList.remove('hidden');
  empty.classList.add('hidden');
  tbody.innerHTML = '';

  const params = new URLSearchParams();
  if (dateFrom.value) params.set('date_from', dateFrom.value);
  if (dateTo.value) params.set('date_to', dateTo.value);
  if (filterCategory.value !== 'Alle') params.set('category', filterCategory.value);
  if (filterType.value !== 'all') params.set('type', filterType.value);
  if (filterMerchant.value.trim()) params.set('merchant', filterMerchant.value.trim());
  params.set('limit', PAGE_SIZE);
  params.set('offset', currentOffset);

  try {
    const resp = await fetch(`/api/transactions?${params}`);
    const data = await resp.json();

    loading.classList.add('hidden');

    // Summary
    statCount.textContent = data.total.toLocaleString('de-DE');
    statDebit.textContent = fmtEur(data.sum_debit);
    statCredit.textContent = fmtEur(data.sum_credit);

    if (data.rows.length === 0) {
      empty.classList.remove('hidden');
      pagination.innerHTML = '';
      return;
    }

    // Render rows
    data.rows.forEach(r => {
      const tr = document.createElement('tr');
      const amountCls = r.type === 'credit' ? 'amount-credit' : 'amount-debit';
      const prefix = r.type === 'credit' ? '+' : '';
      const sourceCls = r.category_source === 'rule' ? 'rule' : r.category_source === 'ai' ? 'ai' : 'manual';

      tr.innerHTML = `
        <td>${fmtDate(r.date)}</td>
        <td title="${esc(r.merchant)}">${esc(r.merchant)}</td>
        <td title="${esc(r.merchant_normalized)}">${esc(r.merchant_normalized)}</td>
        <td class="num ${amountCls}">${prefix}${fmtEur(r.amount)}</td>
        <td>
          <span class="cat-tag" data-merchant="${esc(r.merchant_normalized)}" data-category="${esc(r.category)}" data-display="${esc(r.merchant)}">
            ${esc(r.category)} <span class="edit-icon">\u270E</span>
          </span>
        </td>
        <td><span class="source-badge ${sourceCls}">${esc(r.category_source)}</span></td>
      `;
      tbody.appendChild(tr);
    });

    // Pagination
    renderPagination(data.total);

  } catch (e) {
    loading.classList.add('hidden');
    empty.textContent = 'Fehler beim Laden: ' + e.message;
    empty.classList.remove('hidden');
  }
}

function renderPagination(total) {
  const totalPages = Math.ceil(total / PAGE_SIZE);
  const currentPage = Math.floor(currentOffset / PAGE_SIZE);
  pagination.innerHTML = '';

  if (totalPages <= 1) return;

  const prevBtn = document.createElement('button');
  prevBtn.className = 'page-btn';
  prevBtn.textContent = '\u2190';
  prevBtn.disabled = currentPage === 0;
  prevBtn.addEventListener('click', () => { currentOffset -= PAGE_SIZE; loadTransactions(); });
  pagination.appendChild(prevBtn);

  const info = document.createElement('span');
  info.className = 'page-info';
  info.textContent = `Seite ${currentPage + 1} / ${totalPages} (${total} Transaktionen)`;
  pagination.appendChild(info);

  const nextBtn = document.createElement('button');
  nextBtn.className = 'page-btn';
  nextBtn.textContent = '\u2192';
  nextBtn.disabled = currentPage >= totalPages - 1;
  nextBtn.addEventListener('click', () => { currentOffset += PAGE_SIZE; loadTransactions(); });
  pagination.appendChild(nextBtn);
}

// ── Category edit modal ──

let editingMerchant = null;

tbody.addEventListener('click', e => {
  const tag = e.target.closest('.cat-tag');
  if (!tag) return;

  editingMerchant = {
    merchant_normalized: tag.dataset.merchant,
    category: tag.dataset.category,
    display: tag.dataset.display,
  };

  modalMerchant.textContent = editingMerchant.display;
  modalInfo.textContent = `Aktuell: ${editingMerchant.category}`;
  modalSelect.innerHTML = allCategories.map(c =>
    `<option value="${esc(c)}" ${c === editingMerchant.category ? 'selected' : ''}>${esc(c)}</option>`
  ).join('');
  modalApplyAll.checked = true;
  modal.classList.remove('hidden');
  modalSelect.focus();
});

modalCancel.addEventListener('click', () => modal.classList.add('hidden'));
modal.addEventListener('click', e => { if (e.target === modal) modal.classList.add('hidden'); });

modalOk.addEventListener('click', async () => {
  const newCat = modalSelect.value;
  if (!editingMerchant || newCat === editingMerchant.category) {
    modal.classList.add('hidden');
    return;
  }

  modal.classList.add('hidden');

  if (modalApplyAll.checked) {
    await fetch('/api/recategorize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        merchant_normalized: editingMerchant.merchant_normalized,
        category: newCat,
      }),
    });
  }

  loadTransactions();
});

// ── Events ──

// Quick filter pills
document.querySelector('.quick-filters').addEventListener('click', e => {
  const pill = e.target.closest('.pill');
  if (!pill) return;
  document.querySelectorAll('.quick-filters .pill').forEach(p => p.classList.remove('active'));
  pill.classList.add('active');
  const range = getDateRange(pill.dataset.range);
  dateFrom.value = range.from;
  dateTo.value = range.to;
  currentOffset = 0;
  loadTransactions();
});

// Date inputs
dateFrom.addEventListener('change', () => {
  document.querySelectorAll('.quick-filters .pill').forEach(p => p.classList.remove('active'));
  currentOffset = 0;
  loadTransactions();
});
dateTo.addEventListener('change', () => {
  document.querySelectorAll('.quick-filters .pill').forEach(p => p.classList.remove('active'));
  currentOffset = 0;
  loadTransactions();
});

// Category and type selects
filterCategory.addEventListener('change', () => { currentOffset = 0; loadTransactions(); });
filterType.addEventListener('change', () => { currentOffset = 0; loadTransactions(); });

// Merchant search (debounced)
filterMerchant.addEventListener('input', () => {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => { currentOffset = 0; loadTransactions(); }, 300);
});

// ── Init ──
(async () => {
  await loadCategories();
  // Set default: last month
  const range = getDateRange('last-month');
  dateFrom.value = range.from;
  dateTo.value = range.to;
  loadTransactions();
})();
