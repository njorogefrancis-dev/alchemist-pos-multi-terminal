/* AlchemyPOS 2 — pos.js */
'use strict';

const POS = (() => {
  let cart = [];
  let S = {};         // settings
  let PMs = [];       // payment methods
  let currentCat = 'All';
  let aiEnabled = true;
  let suggestDebounce;

  // ── Bootstrap ──────────────────────────────────────────
  function init(cfg) {
    S  = cfg.settings || {};
    PMs = cfg.paymentMethods || [];
    aiEnabled = S.ai_enabled !== false;
    renderPayBtns();
    bindEvents();
    loadProducts();
    pollAlerts();
    switchMobileTab('products');
  }

  // ── Event binding ──────────────────────────────────────
  function bindEvents() {
    const inp = document.getElementById('pos-search');
    if (!inp) return;
    inp.addEventListener('input', debounce(handleSearch, 350));
    inp.addEventListener('keydown', e => { if (e.key === 'Enter') handleSearch(); });

    document.querySelectorAll('.cat-pill').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.cat-pill').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentCat = btn.dataset.cat || 'All';
        loadProducts();
      });
    });

    document.getElementById('discount-input')?.addEventListener('input', renderCart);
  }

  async function handleSearch() {
    const q = document.getElementById('pos-search')?.value.trim() || '';
    if (!q) { loadProducts(); return; }
    // Try AI search first if enabled
    if (aiEnabled && q.length > 2) {
      await aiSearch(q);
    } else {
      loadProducts();
    }
  }

  // ── AI Search ──────────────────────────────────────────
  async function aiSearch(q) {
    const grid = document.getElementById('product-grid');
    grid.innerHTML = `<div class="no-products"><div class="no-icon spin">⟳</div><p>AI searching…</p></div>`;
    try {
      const data = await api('/api/ai/search', 'POST', { query: q });
      if (data.results && data.results.length) {
        renderGrid(data.results, data.ai);
      } else {
        grid.innerHTML = `<div class="no-products"><div class="no-icon">🔍</div><p>No results for "${escHtml(q)}"</p></div>`;
      }
    } catch { loadProducts(); }
  }

  // ── Load products ──────────────────────────────────────
  async function loadProducts() {
    const q   = document.getElementById('pos-search')?.value.trim() || '';
    const grid = document.getElementById('product-grid');
    try {
      const products = await api(`/api/products?q=${encodeURIComponent(q)}&cat=${encodeURIComponent(currentCat)}`);
      renderGrid(products, false);
    } catch (e) {
      grid.innerHTML = `<div class="no-products"><div class="no-icon">⚠</div><p>${escHtml(e.message)}</p></div>`;
    }
  }

  function renderGrid(products, aiMode = false) {
    const grid = document.getElementById('product-grid');
    if (!products.length) {
      grid.innerHTML = `<div class="no-products"><div class="no-icon">🛒</div><p>No products found</p></div>`;
      return;
    }
    const sym = S.currency_symbol || 'KSh';
    const aiTag = aiMode ? '<span class="pc-badge featured">AI</span>' : '';
    grid.innerHTML = products.map(p => {
      const lowTag = p.is_low && !aiMode ? '<span class="pc-badge low">LOW</span>' : '';
      const featTag = p.is_featured && !aiMode ? '<span class="pc-badge featured">★</span>' : '';
      return `<div class="product-card" onclick="POS.addToCart(${p.id},${JSON.stringify(p.name).replace(/"/g,'&quot;')},${p.price},${p.stock},${JSON.stringify(p.unit).replace(/"/g,'&quot;')})">
        ${aiTag}${featTag}${lowTag}
        <div class="pc-name">${escHtml(p.name)}</div>
        <div class="pc-cat">${escHtml(p.category)}</div>
        <div class="pc-price">${sym} ${Number(p.price).toFixed(2)}</div>
        <!-- stock hidden on POS -->
      </div>`;
    }).join('');
  }

  // ── Cart management ────────────────────────────────────
  function addToCart(id, name, price, stock, unit) {
    const existing = cart.find(i => i.product_id === id);
    if (existing) {
      if (S.track_stock && !S.allow_negative_stock && existing.qty >= stock) {
        showFlash(`Insufficient stock for ${name}`, 'error'); return;
      }
      existing.qty++;
    } else {
      cart.push({ product_id: id, name, price, qty: 1, stock, unit });
    }
    renderCart();
    scheduleAiSuggest();
    if (window.matchMedia('(max-width: 768px)').matches) switchMobileTab('cart');
  }

  function removeFromCart(idx) {
    cart.splice(idx, 1);
    renderCart();
    scheduleAiSuggest();
  }

  function changeQty(idx, delta) {
    const item = cart[idx];
    if (!item) return;
    const nq = item.qty + delta;
    if (nq <= 0) { removeFromCart(idx); return; }
    if (S.track_stock && !S.allow_negative_stock && nq > item.stock) {
      showFlash('Insufficient stock', 'error'); return;
    }
    item.qty = nq;
    renderCart();
  }

  function clearCart() {
    cart = [];
    const di = document.getElementById('discount-input');
    if (di) di.value = '0';
    renderCart();
    hideSuggestions();
  }

  function renderCart() {
    const listEl  = document.getElementById('cart-items');
    const countEl = document.getElementById('cart-count');
    const itemCount = cart.reduce((s, i) => s + i.qty, 0);
    if (countEl) countEl.textContent = itemCount;
    const mobileCount = document.getElementById('cart-count-mobile');
    if (mobileCount) mobileCount.textContent = itemCount;

    if (!cart.length) {
      listEl.innerHTML = `<div class="cart-empty"><div class="empty-icon">🛒</div><span>Cart is empty</span><span style="font-size:10px;color:var(--text3)">Tap products to add</span></div>`;
      updateTotals(0,0,0,0);
      renderPayBtns();
      return;
    }

    const sym = S.currency_symbol || 'KSh';
    listEl.innerHTML = cart.map((item, idx) => `
      <div class="cart-item">
        <div class="ci-name">${escHtml(item.name)}<span>${sym} ${Number(item.price).toFixed(2)} / ${escHtml(item.unit)}</span></div>
        <div class="ci-controls">
          <button class="qty-btn" onclick="POS.changeQty(${idx},-1)">−</button>
          <span class="qty-val">${item.qty}</span>
          <button class="qty-btn" onclick="POS.changeQty(${idx},1)">+</button>
        </div>
        <div class="ci-subtotal">${sym} ${(item.qty * item.price).toFixed(2)}</div>
        <button class="ci-remove" onclick="POS.removeFromCart(${idx})" title="Remove">×</button>
      </div>`).join('');

    const subtotal = cart.reduce((s,i) => s + i.qty * i.price, 0);
    const discount = Math.max(0, parseFloat(document.getElementById('discount-input')?.value || 0) || 0);
    const after    = Math.max(0, subtotal - discount);
    let tax;
    if (S.tax_inclusive) {
      tax = after - after / (1 + S.tax_rate / 100);
    } else {
      tax = after * S.tax_rate / 100;
    }
    const total = S.tax_inclusive ? after : after + tax;
    updateTotals(subtotal, discount, tax, total);
    renderPayBtns();
  }

  function updateTotals(subtotal, discount, tax, total) {
    const sym = S.currency_symbol || 'KSh';
    const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
    set('t-subtotal', `${sym} ${subtotal.toFixed(2)}`);
    set('t-discount', `−${sym} ${discount.toFixed(2)}`);
    set('t-tax',      `${sym} ${tax.toFixed(2)}`);
    const totalFormatted = fmtMoney(total, sym);
    set('t-total', totalFormatted);
    set('peek-total', totalFormatted);
    const peekCount = document.getElementById('peek-count');
    if (peekCount) peekCount.textContent = cart.reduce((s, i) => s + i.qty, 0);
  }

  // ── AI Suggestions ─────────────────────────────────────
  function scheduleAiSuggest() {
    if (!aiEnabled || !cart.length) return;
    clearTimeout(suggestDebounce);
    suggestDebounce = setTimeout(loadAiSuggestions, 1800);
  }

  async function loadAiSuggestions() {
    if (!cart.length) return;
    try {
      const data = await api('/api/ai/suggest', 'POST', { cart: cart.map(i => ({ product_id: i.product_id, name: i.name })) });
      renderSuggestions(data.suggestions || []);
    } catch {}
  }

  function renderSuggestions(items) {
    const el = document.getElementById('ai-suggest-strip');
    const lbl = document.getElementById('ai-suggest-label');
    if (!el) return;
    if (!items.length) { el.classList.add('hidden'); if(lbl) lbl.classList.add('hidden'); return; }
    el.classList.remove('hidden');
    if(lbl) lbl.classList.remove('hidden');
    const sym = S.currency_symbol || 'KSh';
    el.innerHTML = items.map(p =>
      `<div class="ai-suggest-pill" onclick="POS.addToCart(${p.id},${JSON.stringify(p.name).replace(/"/g,'&quot;')},${p.price},999,'pcs')">
        ✦ ${escHtml(p.name)} <span style="opacity:0.7;font-size:10px">${sym} ${Number(p.price).toFixed(2)}</span>
      </div>`
    ).join('');
  }

  function hideSuggestions() {
    const el = document.getElementById('ai-suggest-strip');
    const lbl = document.getElementById('ai-suggest-label');
    if (el) el.classList.add('hidden');
    if (lbl) lbl.classList.add('hidden');
  }

  // ── Payment buttons ────────────────────────────────────
  function renderPayBtns() {
    const container = document.getElementById('pay-grid');
    if (!container) return;
    const disabled = cart.length === 0 ? 'disabled' : '';
    container.innerHTML = PMs.map(pm =>
      `<button class="pay-btn" onclick="POS.openPayment('${pm.name}','${escHtml(pm.label)}')" ${disabled}>
        <span class="pay-icon">${pm.icon || '💳'}</span>
        <span>${escHtml(pm.label)}</span>
      </button>`
    ).join('');
  }

  // ── Payment flow ───────────────────────────────────────
  function openPayment(method, label) {
    if (!cart.length) { showFlash('Cart is empty', 'error'); return; }
    const sym  = S.currency_symbol || 'KSh';
    const subtotal = cart.reduce((s,i) => s + i.qty * i.price, 0);
    const discount = Math.max(0, parseFloat(document.getElementById('discount-input')?.value || 0) || 0);
    const after = Math.max(0, subtotal - discount);
    const tax   = S.tax_inclusive ? after - after/(1+S.tax_rate/100) : after * S.tax_rate/100;
    const total = S.tax_inclusive ? after : after + tax;

    const modal = document.getElementById('payment-modal');
    modal.dataset.method = method;
    modal.dataset.total  = total;

    document.getElementById('pm-title').textContent     = `Pay with ${label}`;
    document.getElementById('pm-total-amount').textContent = fmtMoney(total, sym);
    document.getElementById('pm-cash-section').classList.add('hidden');
    document.getElementById('pm-mpesa-section').classList.add('hidden');

    if (method === 'cash') {
      document.getElementById('pm-cash-section').classList.remove('hidden');
      const inp = document.getElementById('cash-tendered');
      inp.value = total.toFixed(2);
      updateChange();
      setTimeout(() => inp.focus(), 100);
    } else if (['mpesa','paybill','till','send_money','pochi'].includes(method)) {
      document.getElementById('pm-mpesa-section').classList.remove('hidden');
      let detail = '';
      if (method === 'paybill' || method === 'mpesa') detail = S.paybill_number || '—';
      else if (method === 'till') detail = S.till_number || '—';
      else if (method === 'send_money') detail = S.send_money_name || '—';
      else if (method === 'pochi') detail = S.pochi_number || '—';
      const methodLabel = {mpesa:'M-Pesa Paybill', paybill:'Paybill', till:'Till Number', send_money:'Send Money', pochi:'Pochi La Biashara'}[method] || label;
      document.getElementById('pm-account-label').textContent = methodLabel;
      document.getElementById('pm-account-number').textContent = detail;
    }
    openModal('payment-overlay');
  }

  function updateChange() {
    const total    = parseFloat(document.getElementById('payment-modal')?.dataset.total || 0);
    const tendered = parseFloat(document.getElementById('cash-tendered')?.value || 0);
    const change   = tendered - total;
    const el       = document.getElementById('change-display');
    const sym      = S.currency_symbol || 'KSh';
    if (el) {
      el.textContent = fmtMoney(change, sym);
      el.className   = 'change-display' + (change < 0 ? ' negative' : '');
    }
  }

  async function confirmPayment() {
    const modal   = document.getElementById('payment-modal');
    const method  = modal.dataset.method;
    const total   = parseFloat(modal.dataset.total);
    let tendered  = total;

    if (method === 'cash') {
      tendered = parseFloat(document.getElementById('cash-tendered')?.value || 0);
      if (tendered < total) { showFlash('Tendered amount is less than total', 'error'); return; }
    }
    const discount = Math.max(0, parseFloat(document.getElementById('discount-input')?.value || 0) || 0);
    const btn = document.getElementById('confirm-pay-btn');
    setLoading(btn, true, 'Processing…');
    try {
      const data = await api('/api/sale', 'POST', {
        items: cart.map(i => ({ product_id: i.product_id, name: i.name, qty: i.qty, price: i.price })),
        discount, payment_method: method, amount_tendered: tendered
      });
      closeModal('payment-overlay');
      showReceipt(data.receipt);
      clearCart();
      loadProducts();
      pollAlerts();
    } catch (e) { showFlash(e.message, 'error'); }
    finally { setLoading(btn, false); }
  }

  // ── Receipt ────────────────────────────────────────────
  function showReceipt(r) {
    const sym = r.currency || 'KSh';
    const items = r.items.map(i =>
      `<div class="receipt-row"><span>${escHtml(i.name)} ×${i.qty}</span><span>${sym} ${Number(i.subtotal).toFixed(2)}</span></div>`
    ).join('');
    const taxLine = r.show_tax
      ? `<div class="receipt-row"><span>${escHtml(r.tax_name)}</span><span>${sym} ${Number(r.tax).toFixed(2)}</span></div>` : '';
    const changeLine = r.payment_method === 'cash'
        ? `<div class="receipt-row"><span>Tendered</span><span>${sym} ${Number(r.amount_tendered).toFixed(2)}</span></div><div class="receipt-row"><span>Change</span><span>${sym} ${Number(r.change).toFixed(2)}</span></div>`
        : '';

    document.getElementById('receipt-content').innerHTML = `
      <div class="receipt-paper">
        <div class="receipt-shop">
          <h2>${escHtml(r.shop_name)}</h2>
          ${r.shop_address ? `<div style="color:var(--text3);font-size:11px">${escHtml(r.shop_address)}</div>` : ''}
          ${r.shop_phone   ? `<div style="color:var(--text3);font-size:11px">📞 ${escHtml(r.shop_phone)}</div>` : ''}
          ${r.receipt_header ? `<div style="margin-top:8px;color:var(--text2);font-size:11px">${escHtml(r.receipt_header)}</div>` : ''}
        </div>
        <hr class="receipt-divider">
        <div class="receipt-row" style="color:var(--text3);font-size:10px">
          <span>Receipt: ${escHtml(r.receipt_number)}</span>
          <span>${escHtml(r.date)}</span>
        </div>
        <div style="color:var(--text3);font-size:10px;padding:2px 0 6px">Cashier: ${escHtml(r.cashier)}</div>
        <hr class="receipt-divider">
        ${items}
        <hr class="receipt-divider">
        <div class="receipt-row"><span>Subtotal</span><span>${sym} ${Number(r.subtotal).toFixed(2)}</span></div>
        ${r.discount > 0 ? `<div class="receipt-row"><span>Discount</span><span style="color:var(--green)">−${sym} ${Number(r.discount).toFixed(2)}</span></div>` : ''}
        ${taxLine}
        <div class="receipt-total"><span>TOTAL</span><span>${sym} ${Number(r.total).toFixed(2)}</span></div>
        <hr class="receipt-divider">
        <div class="receipt-row"><span>Payment</span><span>${escHtml(r.payment_method.toUpperCase())}</span></div>
        ${changeLine}
        ${r.receipt_footer ? `<hr class="receipt-divider"><div class="receipt-foot">${escHtml(r.receipt_footer)}</div>` : ''}
      </div>`;
    openModal('receipt-overlay');
    if (S.auto_print_receipt) setTimeout(() => window.print(), 400);
  }

  function printReceipt() { window.print(); }

  // ── Stock alerts polling ───────────────────────────────
  async function pollAlerts() {
    try {
      const data = await api('/api/stock-alerts');
      const el = document.getElementById('pos-alerts');
      if (!el) return;
      const all = [
        ...data.out_of_stock.map(i => ({ ...i, type: 'out' })),
        ...data.low_stock.map(i => ({ ...i, type: 'low' })),
      ];
      const badge = document.getElementById('alerts-badge');
      if (badge) { badge.textContent = all.length; badge.style.display = all.length ? '' : 'none'; }
      if (!all.length) { el.innerHTML = '<div style="padding:8px;color:var(--text3);font-size:11px">✓ All stock levels OK</div>'; return; }
      el.innerHTML = all.map(i =>
        `<div class="alert-pill ${i.type}">
          <span>${escHtml(i.name)}</span>
          <span class="pill-qty">${i.type === 'out' ? 'OUT' : i.stock + ' ' + (i.unit || '')}</span>
        </div>`
      ).join('');
    } catch {}
  }

  setInterval(pollAlerts, 25000);

  function switchMobileTab(tab) {
    const productsPanel = document.querySelector('[data-mobile-panel="products"]');
    const cartPanel = document.querySelector('[data-mobile-panel="cart"]');
    if (!productsPanel || !cartPanel) return;
    const showCart = tab === 'cart';
    productsPanel.classList.toggle('mobile-hidden', showCart);
    cartPanel.classList.toggle('mobile-hidden', !showCart);
    document.querySelectorAll('.pos-tab-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.tab === tab);
    });
  }

  // Public API
  return { init, addToCart, removeFromCart, changeQty, clearCart, openPayment, updateChange, confirmPayment, printReceipt, loadProducts, switchMobileTab };
})();
