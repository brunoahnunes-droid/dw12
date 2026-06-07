'use strict';

/* ── Mobile sidebar drawer ───────────────────────────────────── */
function openSidebar() {
  document.getElementById('sidebar')?.classList.add('open');
  document.getElementById('sidebar-backdrop')?.classList.add('open');
}
function closeSidebar() {
  document.getElementById('sidebar')?.classList.remove('open');
  document.getElementById('sidebar-backdrop')?.classList.remove('open');
}
function toggleSidebar() {
  const sb = document.getElementById('sidebar');
  if (sb && sb.classList.contains('open')) closeSidebar();
  else openSidebar();
}
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeSidebar(); });

/* ── Toast notifications ─────────────────────────────────────── */
function showToast(msg, type = 'success') {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }
  const icons = { success: '✅', error: '❌', info: 'ℹ️', warn: '⚠️' };
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${icons[type] || '•'}</span><span>${msg}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.animation = 'fadeOut .3s forwards';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

/* ── Number picker grid ──────────────────────────────────────── */
class NumberPicker {
  constructor(containerId, opts) {
    this.container  = document.getElementById(containerId);
    this.lo         = opts.lo || 1;
    this.hi         = opts.hi || 60;
    this.minSel     = opts.min || 6;
    this.maxSel     = opts.max || 20;
    this.brandColor = opts.color || '#f5a623';
    this.inputId    = opts.inputId || 'selected-numbers';
    this.counterId  = opts.counterId || 'sel-count';
    this.fixed      = opts.fixed || false;
    this.positional = opts.positional || false;
    this.selected   = new Set();
    this.render();
  }

  render() {
    this.container.innerHTML = '';
    const grid = document.createElement('div');
    grid.className = 'num-grid';
    for (let n = this.lo; n <= this.hi; n++) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'num-btn';
      btn.textContent = String(n).padStart(2, '0');
      btn.dataset.n = n;
      btn.addEventListener('click', () => this.toggle(n, btn));
      grid.appendChild(btn);
    }
    this.container.appendChild(grid);
    this.updateInput();
  }

  toggle(n, btn) {
    if (this.selected.has(n)) {
      this.selected.delete(n);
      btn.classList.remove('selected');
    } else if (this.selected.size < this.maxSel) {
      this.selected.add(n);
      btn.classList.add('selected');
    } else {
      showToast(`Máximo ${this.maxSel} números para este jogo.`, 'warn');
      return;
    }
    this.updateInput();
    this.updateCounter();
  }

  updateInput() {
    const inp = document.getElementById(this.inputId);
    if (inp) inp.value = [...this.selected].sort((a, b) => a - b).join(',');
  }

  updateCounter() {
    const el = document.getElementById(this.counterId);
    if (!el) return;
    const n = this.selected.size;
    el.innerHTML = `<span class="sel-counter">${n}</span>`
                 + `<span class="sel-max"> / ${this.minSel}`
                 + (this.minSel !== this.maxSel ? `–${this.maxSel}` : '')
                 + ` selecionados</span>`;
    const ok = n >= this.minSel && n <= this.maxSel;
    el.style.color = ok ? 'var(--accent)' : 'var(--muted)';
    const btn = document.getElementById('add-btn');
    if (btn) btn.disabled = !ok;
  }

  highlightDraw(nums) {
    document.querySelectorAll('.num-btn').forEach(btn => {
      const n = +btn.dataset.n;
      btn.classList.toggle('drawn-mark', nums.includes(n));
    });
  }

  reset() {
    this.selected.clear();
    document.querySelectorAll('.num-btn').forEach(b => b.classList.remove('selected'));
    this.updateInput();
    this.updateCounter();
  }
}

/* ── Lottery type selector (reload form section) ─────────────── */
function onLotteryChange(selectEl, formId) {
  const form = document.getElementById(formId);
  if (form) form.submit();
}

/* ── Generator: update cost preview ─────────────────────────── */
function nCombinations(n, k) {
  if (k < 0 || n < 0 || k > n) return 0;
  if (k === 0 || k === n) return 1;
  k = Math.min(k, n - k);
  let c = 1;
  for (let i = 0; i < k; i++) c = (c * (n - i)) / (i + 1);
  return Math.round(c);
}

function updateCost(price, drawCount) {
  const gamesEl = document.getElementById('n-games');
  const picksEl = document.getElementById('n-picks');
  const costEl  = document.getElementById('cost-preview');
  if (!gamesEl || !costEl) return;
  const g     = parseInt(gamesEl.value) || 0;
  const picks = picksEl ? (parseInt(picksEl.value) || drawCount) : drawCount;
  const combos  = drawCount ? nCombinations(picks, drawCount) : 1;
  const perGame = (combos || 1) * parseFloat(price || 0);
  const cost    = g * perGame;
  costEl.textContent = `💰 Investimento: R$ ${cost.toFixed(2).replace('.', ',')}`;
}

/* ── Confirm before dangerous actions ───────────────────────── */
function confirmAction(msg, formId) {
  if (confirm(msg)) {
    document.getElementById(formId)?.submit();
    return true;
  }
  return false;
}

/* ── Table row click → select ────────────────────────────────── */
function initTableSelect(tableId, hiddenId) {
  const table = document.getElementById(tableId);
  const hidden = document.getElementById(hiddenId);
  if (!table || !hidden) return;
  table.querySelectorAll('tbody tr').forEach(row => {
    row.style.cursor = 'pointer';
    row.addEventListener('click', () => {
      table.querySelectorAll('tbody tr').forEach(r => r.style.outline = '');
      row.style.outline = '2px solid var(--accent)';
      hidden.value = row.dataset.id || '';
    });
  });
}

/* ── Flash message auto dismiss ─────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.flash-msg').forEach(el => {
    const type = el.dataset.type || 'info';
    showToast(el.textContent, type);
    el.remove();
  });
});

/* ── Loading overlay ─────────────────────────────────────────── */
const _overlay = () => document.getElementById('loading-overlay');

function showLoading(msg) {
  const el = _overlay();
  if (!el) return;
  const msgEl = document.getElementById('loading-msg');
  if (msgEl) msgEl.textContent = msg || 'Aguarde…';
  el.style.display = 'flex';
}

function hideLoading() {
  const el = _overlay();
  if (el) el.style.display = 'none';
}

// Show loading on any form submit (except ones marked data-no-load)
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('form:not([data-no-load])').forEach(form => {
    form.addEventListener('submit', () => {
      const action = form.querySelector('[name="action"]')?.value;
      const msgs = {
        'combine': 'Gerando combinações…',
        'save':    'Salvando jogos…',
        'conferir': 'Conferindo sorteio…',
        'importar': 'Importando resultados…',
      };
      showLoading(msgs[action] || 'Processando…');
    });
  });
});

/* ── Picks slider display ────────────────────────────────────── */
function syncSlider(sliderId, labelId, suffix = ' números') {
  const s = document.getElementById(sliderId);
  const l = document.getElementById(labelId);
  if (!s || !l) return;
  l.textContent = s.value + suffix;
  s.addEventListener('input', () => { l.textContent = s.value + suffix; });
}
