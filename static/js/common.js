/* AlchemyPOS 2 — common.js */
'use strict';

// ── Flash messages ──────────────────────────────────────
function showFlash(msg, type = 'info', ms = 4200) {
  let stack = document.getElementById('flash-stack');
  if (!stack) {
    stack = document.createElement('div');
    stack.id = 'flash-stack';
    stack.className = 'flash-stack';
    document.body.appendChild(stack);
  }
  const el = document.createElement('div');
  const icons = { success: '✓', error: '✕', info: 'ℹ', warning: '⚠' };
  el.className = `flash flash-${type}`;
  el.innerHTML = `<span>${icons[type] || 'ℹ'}</span><span style="flex:1">${msg}</span><button class="flash-close" onclick="this.parentElement.remove()">×</button>`;
  stack.appendChild(el);
  setTimeout(() => { el.style.opacity = '0'; el.style.transform = 'translateX(10px)'; el.style.transition = '0.3s'; setTimeout(() => el.remove(), 300); }, ms);
}

// ── CSRF token ───────────────────────────────────────────
function csrfToken() {
  return document.querySelector('meta[name="csrf-token"]')?.content || '';
}

// ── API helper ───────────────────────────────────────────
async function api(url, method = 'GET', body = null, opts = {}) {
  const options = {
    method,
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
    ...opts
  };
  if (body) options.body = JSON.stringify(body);
  const res = await fetch(url, options);
  let data;
  try { data = await res.json(); } catch { data = {}; }
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

async function apiForm(url, formData) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'X-CSRFToken': csrfToken() },
    body: formData
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

// ── Modal helpers ────────────────────────────────────────
function openModal(id) { document.getElementById(id)?.classList.add('open'); }
function closeModal(id) { document.getElementById(id)?.classList.remove('open'); }
function closeAllModals() {
  document.querySelectorAll('.modal-overlay.open').forEach(m => m.classList.remove('open'));
}

document.addEventListener('click', e => {
  if (e.target.classList.contains('modal-overlay')) e.target.classList.remove('open');
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeAllModals();
});

// ── Format helpers ───────────────────────────────────────
function fmtMoney(n, sym = 'KSh') {
  return `${sym} ${Number(n).toLocaleString('en-KE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
function escHtml(s) {
  if (s == null) return '';
  const d = document.createElement('div');
  d.textContent = String(s);
  return d.innerHTML;
}
function debounce(fn, ms = 300) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

// ── Confirm ──────────────────────────────────────────────
function confirmAction(msg) { return window.confirm(msg); }

// ── Active nav link ──────────────────────────────────────
(function highlightNav() {
  const path = window.location.pathname;
  document.querySelectorAll('.nav-item[href]').forEach(a => {
    if (a.getAttribute('href') === path ||
        (path.startsWith(a.getAttribute('href')) && a.getAttribute('href').length > 1)) {
      a.classList.add('active');
    }
  });
})();

function toggleMobileMore(open) {
  const sheet = document.getElementById('mobile-more-sheet');
  const overlay = document.getElementById('mobile-more-overlay');
  if (!sheet || !overlay) return;
  const shouldOpen = typeof open === 'boolean' ? open : !sheet.classList.contains('open');
  sheet.classList.toggle('open', shouldOpen);
  overlay.classList.toggle('open', shouldOpen);
}

document.addEventListener('click', e => {
  if (e.target.classList.contains('mobile-more-link')) toggleMobileMore(false);
});

window.addEventListener('resize', debounce(() => {
  if (window.matchMedia('(min-width: 769px)').matches) toggleMobileMore(false);
}, 120));

// ── Loading spinner helper ───────────────────────────────
function setLoading(btn, loading, text = '') {
  if (!btn) return;
  if (loading) {
    btn._orig = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<span class="spin" style="display:inline-block">⟳</span> ${text || 'Loading…'}`;
  } else {
    btn.disabled = false;
    if (btn._orig) btn.innerHTML = btn._orig;
  }
}
