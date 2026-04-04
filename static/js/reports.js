/* AlchemyPOS 2 — reports.js */
'use strict';

const RPT = (() => {
  let currency = 'KSh';
  let currentPage = 1;
  let hourlyChart = null;

  function init(cfg) {
    currency = cfg.currency || 'KSh';
    bindFilters();
    loadAll();
  }

  function getParams() {
    const p = new URLSearchParams();
    const set = (id, key) => { const v = document.getElementById(id)?.value; if (v) p.set(key, v); };
    set('f-from',    'date_from');
    set('f-to',      'date_to');
    set('f-cashier', 'cashier_id');
    set('f-method',  'payment_method');
    set('f-search',  'search');
    p.set('page', currentPage);
    return p;
  }

  function bindFilters() {
    document.querySelectorAll('.filter-input').forEach(el =>
      el.addEventListener('change', () => { currentPage = 1; loadAll(); })
    );
    document.getElementById('f-search')?.addEventListener('input', debounce(() => {
      currentPage = 1;
      loadAll();
    }, 350));
    document.getElementById('btn-today')?.addEventListener('click',  () => setQuick('today'));
    document.getElementById('btn-week')?.addEventListener('click',   () => setQuick('week'));
    document.getElementById('btn-month')?.addEventListener('click',  () => setQuick('month'));
    document.getElementById('btn-year')?.addEventListener('click',   () => setQuick('year'));
    document.getElementById('btn-clear')?.addEventListener('click',  clearFilters);
    document.getElementById('btn-ai-summary')?.addEventListener('click', loadAiSummary);
  }

  function setQuick(q) {
    const today = new Date();
    const fmt   = d => d.toISOString().split('T')[0];
    let from = today, to = today;
    if (q === 'week')  { from = new Date(today); from.setDate(today.getDate() - today.getDay()); }
    else if (q === 'month') { from = new Date(today.getFullYear(), today.getMonth(), 1); }
    else if (q === 'year')  { from = new Date(today.getFullYear(), 0, 1); }
    document.getElementById('f-from').value = fmt(from);
    document.getElementById('f-to').value   = fmt(to);
    currentPage = 1; loadAll();
  }

  function clearFilters() {
    ['f-from','f-to','f-cashier','f-method','f-search'].forEach(id => {
      const el = document.getElementById(id); if (el) el.value = '';
    });
    currentPage = 1; loadAll();
  }

  async function loadAll() {
    await Promise.all([loadSummary(), loadSales(), loadTopProducts(), loadPaymentSplit(), loadByCashier(), loadHourly()]);
  }

  async function loadSummary() {
    try {
      const d = await api(`/api/reports/summary?${getParams()}`);
      const sym = d.currency || currency;
      const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
      set('kpi-transactions', d.transactions.toLocaleString());
      set('kpi-revenue',   fmtMoney(d.revenue,   sym));
      set('kpi-discounts', fmtMoney(d.discounts, sym));
      set('kpi-avg',       fmtMoney(d.avg_sale,  sym));
      set('kpi-tax',       fmtMoney(d.tax,       sym));
      set('kpi-profit',    fmtMoney(d.profit,    sym));
    } catch {}
  }

  async function loadSales() {
    try {
      const d     = await api(`/api/reports/sales?${getParams()}`);
      const tbody = document.getElementById('sales-tbody');
      if (!tbody) return;
      if (!d.sales.length) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted" style="padding:24px">No sales found</td></tr>';
        const mob = document.getElementById('reports-sales-mobile');
        if (mob) mob.innerHTML = '<div class="card text-center text-muted">No sales found</div>';
        document.getElementById('pagination').innerHTML = '';
        return;
      }
      const rows = d.sales.map(s => `
        <tr onclick="RPT.viewSale(${s.id})" style="cursor:pointer">
          <td class="text-mono text-amber">${escHtml(s.receipt_number)}</td>
          <td class="text-muted" style="font-size:11px">${escHtml(s.date)}</td>
          <td>${escHtml(s.cashier)}</td>
          <td><span class="badge badge-blue">${escHtml(s.payment_method)}</span></td>
          <td class="text-mono text-amber text-right">${s.currency} ${Number(s.total).toFixed(2)}</td>
          <td><button class="btn btn-xs" onclick="RPT.viewSale(${s.id});event.stopPropagation()">View</button></td>
        </tr>`).join('');
      tbody.innerHTML = rows;
      const mob = document.getElementById('reports-sales-mobile');
      if (mob) {
        mob.innerHTML = d.sales.map(s => `
          <div class="card rpt-mobile-sale" onclick="RPT.viewSale(${s.id})">
            <div class="rpt-mobile-head">
              <strong class="text-mono text-amber">${escHtml(s.receipt_number)}</strong>
              <span class="badge badge-blue">${escHtml(s.payment_method)}</span>
            </div>
            <div class="text-muted" style="font-size:11px">${escHtml(s.date)} • ${escHtml(s.cashier)}</div>
            <div class="rpt-mobile-total">${s.currency} ${Number(s.total).toFixed(2)}</div>
          </div>`).join('');
      }
      renderPagination(d.page, d.pages);
    } catch {}
  }

  function renderPagination(page, pages) {
    const el = document.getElementById('pagination');
    if (!el || pages <= 1) { if (el) el.innerHTML = ''; return; }
    let html = '';
    if (page > 1) html += `<button class="page-btn" onclick="RPT.goPage(${page-1})">◀</button>`;
    for (let i = Math.max(1,page-2); i <= Math.min(pages,page+2); i++) {
      html += `<button class="page-btn ${i===page?'active':''}" onclick="RPT.goPage(${i})">${i}</button>`;
    }
    if (page < pages) html += `<button class="page-btn" onclick="RPT.goPage(${page+1})">▶</button>`;
    el.innerHTML = html;
  }

  function goPage(p) { currentPage = p; loadSales(); }

  async function viewSale(id) {
    try {
      const s   = await api(`/api/reports/sale/${id}`);
      const sym = s.currency || currency;
      document.getElementById('sale-detail-body').innerHTML = `
        <div class="receipt-paper">
          <div class="receipt-shop"><strong style="font-size:14px">${escHtml(s.receipt_number)}</strong></div>
          <div style="color:var(--text3);font-size:11px;margin:6px 0">${escHtml(s.date)} — ${escHtml(s.cashier)}</div>
          <hr class="receipt-divider">
          ${s.items.map(i => `<div class="receipt-row"><span>${escHtml(i.name)} ×${i.qty}</span><span>${sym} ${Number(i.subtotal).toFixed(2)}</span></div>`).join('')}
          <hr class="receipt-divider">
          <div class="receipt-row"><span>Subtotal</span><span>${sym} ${Number(s.subtotal).toFixed(2)}</span></div>
          ${s.discount > 0 ? `<div class="receipt-row"><span>Discount</span><span style="color:var(--green)">−${sym} ${Number(s.discount).toFixed(2)}</span></div>` : ''}
          <div class="receipt-row"><span>Tax</span><span>${sym} ${Number(s.tax).toFixed(2)}</span></div>
          <div class="receipt-total"><span>TOTAL</span><span>${sym} ${Number(s.total).toFixed(2)}</span></div>
          <hr class="receipt-divider">
          <div class="receipt-row"><span>Payment</span><span>${escHtml(s.payment_method.toUpperCase())}</span></div>
          ${s.payment_method==='cash' ? `<div class="receipt-row"><span>Tendered</span><span>${sym} ${Number(s.amount_tendered).toFixed(2)}</span></div><div class="receipt-row"><span>Change</span><span>${sym} ${Number(s.change_given).toFixed(2)}</span></div>` : ''}
        </div>`;
      openModal('sale-detail-modal');
    } catch (e) { showFlash(e.message, 'error'); }
  }

  async function loadTopProducts() {
    try {
      const data = await api(`/api/reports/top-products?${getParams()}`);
      const el = document.getElementById('top-products-body');
      if (!el) return;
      if (!data.length) { el.innerHTML = '<tr><td colspan="3" class="text-muted text-center" style="padding:12px">No data</td></tr>'; return; }
      el.innerHTML = data.map((p,i) => `<tr>
        <td><span class="badge badge-gray" style="margin-right:6px">${i+1}</span>${escHtml(p.name)}</td>
        <td class="text-right text-mono">${Number(p.qty).toFixed(0)}</td>
        <td class="text-right text-amber text-mono">${currency} ${Number(p.revenue).toFixed(2)}</td>
      </tr>`).join('');
      renderSideMobile();
    } catch {}
  }

  async function loadPaymentSplit() {
    try {
      const data = await api(`/api/reports/payment-split?${getParams()}`);
      const el = document.getElementById('payment-split-body');
      if (!el) return;
      if (!data.length) { el.innerHTML = '<tr><td colspan="3" class="text-muted text-center" style="padding:12px">No data</td></tr>'; return; }
      el.innerHTML = data.map(p => `<tr>
        <td><span class="badge badge-blue">${escHtml(p.method)}</span></td>
        <td class="text-right text-mono">${p.count}</td>
        <td class="text-right text-amber text-mono">${currency} ${Number(p.total).toFixed(2)}</td>
      </tr>`).join('');
      renderSideMobile();
    } catch {}
  }

  async function loadByCashier() {
    try {
      const data = await api(`/api/reports/by-cashier?${getParams()}`);
      const el = document.getElementById('cashier-body');
      if (!el) return;
      if (!data.length) { el.innerHTML = '<tr><td colspan="3" class="text-muted text-center" style="padding:12px">No data</td></tr>'; return; }
      el.innerHTML = data.map(c => `<tr>
        <td>${escHtml(c.name)}</td>
        <td class="text-right text-mono">${c.transactions}</td>
        <td class="text-right text-amber text-mono">${currency} ${Number(c.revenue).toFixed(2)}</td>
      </tr>`).join('');
      renderSideMobile();
    } catch {}
  }

  function renderSideMobile() {
    const host = document.getElementById('reports-side-mobile');
    const top = document.getElementById('top-products-body');
    const pay = document.getElementById('payment-split-body');
    const cashier = document.getElementById('cashier-body');
    if (!host || !top || !pay || !cashier) return;
    host.innerHTML = `
      <div class="card"><div class="card-title">Top Products</div><div class="table-wrap"><table><tbody>${top.innerHTML}</tbody></table></div></div>
      <div class="card"><div class="card-title">Payment Methods</div><div class="table-wrap"><table><tbody>${pay.innerHTML}</tbody></table></div></div>
      <div class="card"><div class="card-title">By Cashier</div><div class="table-wrap"><table><tbody>${cashier.innerHTML}</tbody></table></div></div>
    `;
  }

  async function loadHourly() {
    try {
      const data = await api(`/api/reports/hourly?${getParams()}`);
      const el = document.getElementById('hourly-chart');
      if (!el) return;
      const max = Math.max(...data.map(d => d.revenue), 1);
      el.innerHTML = `<div style="display:flex;align-items:flex-end;gap:3px;height:120px;padding:0 4px">
        ${data.map(h => {
          const pct = (h.revenue / max) * 100;
          const color = pct > 70 ? 'var(--amber)' : pct > 30 ? 'var(--blue)' : 'var(--border2)';
          return `<div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:3px;cursor:default" title="${h.hour}:00 — ${currency} ${h.revenue.toFixed(2)}">
            <div style="flex:1;width:100%;display:flex;align-items:flex-end">
              <div style="width:100%;height:${Math.max(pct,2)}%;background:${color};border-radius:2px 2px 0 0;transition:height 0.4s"></div>
            </div>
            <span style="font-size:8px;color:var(--text3);font-family:var(--font-mono)">${h.hour}</span>
          </div>`;
        }).join('')}
      </div>`;
    } catch {}
  }

  async function loadAiSummary() {
    const el  = document.getElementById('ai-summary-text');
    const btn = document.getElementById('btn-ai-summary');
    if (!el) return;
    el.textContent = 'Analysing your data…';
    setLoading(btn, true, 'Thinking…');
    try {
      const data = await api(`/api/reports/ai-summary?${getParams()}`, 'POST');
      el.textContent = data.summary;
    } catch (e) { el.textContent = 'AI analysis unavailable.'; }
    finally { setLoading(btn, false); }
  }

  function exportData(fmt) {
    window.location.href = `/api/reports/export/${fmt}?${getParams()}`;
  }

  return { init, goPage, viewSale, exportData };
})();
