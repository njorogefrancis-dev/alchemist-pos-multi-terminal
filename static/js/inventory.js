/* AlchemyPOS 2 — inventory.js */
'use strict';

const INV = (() => {
  let S = {};
  let currentId = null;

  function init(cfg) {
    S = cfg || {};
    loadProducts();
    loadAlerts();
    setInterval(loadAlerts, 30000);
    document.getElementById('inv-search')?.addEventListener('input', debounce(loadProducts, 300));
    document.getElementById('inv-cat-filter')?.addEventListener('change', loadProducts);
  }

  async function loadProducts() {
    const q   = document.getElementById('inv-search')?.value || '';
    const cat = document.getElementById('inv-cat-filter')?.value || '';
    const tbody = document.getElementById('inv-tbody');
    try {
      const products = await api(`/api/inventory/products?q=${encodeURIComponent(q)}&cat=${encodeURIComponent(cat)}`);
      renderTable(products);
    } catch (e) { showFlash(e.message, 'error'); }
  }

  function renderTable(products) {
    const tbody = document.getElementById('inv-tbody');
    const mobileList = document.getElementById('inv-mobile-list');
    if (!tbody) return;
    const sym = S.currency_symbol || 'KSh';
    if (!products.length) {
      tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted" style="padding:24px">No products found</td></tr>';
      if (mobileList) mobileList.innerHTML = '<div class="card text-center text-muted">No products found</div>';
      return;
    }
    const rowHtml = products.map(p => {
      const stock = p.stock;
      const max   = Math.max(stock, p.low_stock_threshold * 3);
      const pct   = max > 0 ? Math.min(100, (stock / max) * 100) : 0;
      const cls   = stock <= 0 ? 'out' : stock <= p.low_stock_threshold ? 'low' : 'ok';
      const statusBadge = stock <= 0
        ? '<span class="badge badge-red">OUT</span>'
        : stock <= p.low_stock_threshold
        ? '<span class="badge badge-yellow">LOW</span>'
        : '<span class="badge badge-green">OK</span>';
      return `<tr data-id="${p.id}" onclick="INV.selectProduct(${p.id})" class="${currentId===p.id?'active':''}">
        <td><div style="font-weight:600;color:var(--text)">${escHtml(p.name)}</div>${p.barcode ? `<div class="td-mono" style="font-size:10px">${escHtml(p.barcode)}</div>` : ''}</td>
        <td><span class="badge badge-gray">${escHtml(p.category)}</span></td>
        <td class="text-mono text-amber">${sym} ${p.price.toFixed(2)}</td>
        <td class="text-mono text-muted">${sym} ${p.cost.toFixed(2)}</td>
        <td>
          <div class="stock-bar-wrap">
            <div class="stock-bar"><div class="stock-bar-fill ${cls}" style="width:${pct}%"></div></div>
            <span class="text-mono" style="font-size:11px">${stock} ${escHtml(p.unit)}</span>
          </div>
        </td>
        <td>${statusBadge}</td>
        <td><span class="${p.margin > 0 ? 'text-green' : 'text-muted'} text-mono" style="font-size:11px">${p.margin}%</span></td>
        <td>
          <div style="display:flex;gap:4px">
            <button class="btn btn-xs" onclick="INV.openEdit(${p.id});event.stopPropagation()">Edit</button>
            <button class="btn btn-xs" onclick="INV.openAdjust(${p.id});event.stopPropagation()">±</button>
            <button class="btn btn-xs btn-danger" onclick="INV.deleteProduct(${p.id},event)">✕</button>
          </div>
        </td>
      </tr>`;
    }).join('');
    tbody.innerHTML = rowHtml;

    if (mobileList) {
      mobileList.innerHTML = products.map(p => {
        const stock = p.stock;
        const cls   = stock <= 0 ? 'badge-red' : stock <= p.low_stock_threshold ? 'badge-yellow' : 'badge-green';
        return `<div class="card inv-mobile-card" data-id="${p.id}" onclick="INV.selectProduct(${p.id})">
          <div class="inv-mobile-head">
            <strong>${escHtml(p.name)}</strong>
            <span class="badge ${cls}">${stock <= 0 ? 'OUT' : stock <= p.low_stock_threshold ? 'LOW' : 'OK'}</span>
          </div>
          <div class="inv-mobile-meta">${escHtml(p.category)} • ${escHtml(p.unit)} • ${p.stock}</div>
          <div class="inv-mobile-price">${sym} ${p.price.toFixed(2)} <span class="text-muted">cost ${sym} ${p.cost.toFixed(2)}</span></div>
          <div style="display:flex;gap:6px;margin-top:10px">
            <button class="btn btn-xs" onclick="INV.openEdit(${p.id});event.stopPropagation()">Edit</button>
            <button class="btn btn-xs" onclick="INV.openAdjust(${p.id});event.stopPropagation()">Stock</button>
            <button class="btn btn-xs btn-danger" onclick="INV.deleteProduct(${p.id},event)">Delete</button>
          </div>
        </div>`;
      }).join('');
    }
  }

  async function selectProduct(id) {
    currentId = id;
    document.querySelectorAll('#inv-tbody tr').forEach(r => r.classList.toggle('active', +r.dataset.id === id));
    try {
      const p = await api(`/api/inventory/product/${id}`);
      renderDetail(p);
    } catch {}
  }

  function renderDetail(p) {
    const panel = document.getElementById('product-detail-panel');
    if (!panel) return;
    const sym = S.currency_symbol || 'KSh';
    panel.innerHTML = `
      <div class="card-title">Product Detail</div>
      <div style="display:flex;flex-direction:column;gap:10px;font-size:12px">
        <div style="display:flex;justify-content:space-between"><span class="text-muted">Name</span><strong>${escHtml(p.name)}</strong></div>
        <div style="display:flex;justify-content:space-between"><span class="text-muted">Category</span><span class="badge badge-gray">${escHtml(p.category)}</span></div>
        ${p.barcode ? `<div style="display:flex;justify-content:space-between"><span class="text-muted">Barcode</span><span class="text-mono">${escHtml(p.barcode)}</span></div>` : ''}
        <div style="display:flex;justify-content:space-between"><span class="text-muted">Price</span><strong class="text-amber text-mono">${sym} ${p.price.toFixed(2)}</strong></div>
        <div style="display:flex;justify-content:space-between"><span class="text-muted">Cost</span><span class="text-mono">${sym} ${p.cost.toFixed(2)}</span></div>
        <div style="display:flex;justify-content:space-between"><span class="text-muted">Margin</span><span class="${p.margin>0?'text-green':'text-muted'} text-mono">${p.margin}%</span></div>
        <div style="display:flex;justify-content:space-between"><span class="text-muted">Unit</span><span>${escHtml(p.unit)}</span></div>
        <div style="display:flex;justify-content:space-between"><span class="text-muted">Stock</span><strong class="text-mono">${p.stock}</strong></div>
        <div style="display:flex;justify-content:space-between"><span class="text-muted">Low At</span><span class="text-mono">${p.low_stock_threshold}</span></div>
        <div style="display:flex;justify-content:space-between"><span class="text-muted">Updated</span><span class="text-muted">${p.updated_at}</span></div>
      </div>
      <div style="display:flex;gap:6px;margin-top:14px">
        <button class="btn btn-primary btn-sm" onclick="INV.openEdit(${p.id})">Edit</button>
        <button class="btn btn-sm" onclick="INV.openAdjust(${p.id})">Adjust Stock</button>
      </div>`;
    document.getElementById('product-detail-card').style.display = '';
  }

  function openAdd() {
    document.getElementById('product-form').reset();
    document.getElementById('product-id').value = '';
    document.getElementById('pm-modal-title').textContent = 'Add Product';
    document.getElementById('stock-init-group').style.display = '';
    openModal('product-modal');
  }

  async function openEdit(id) {
    try {
      const p = await api(`/api/inventory/product/${id}`);
      document.getElementById('product-id').value = p.id;
      document.getElementById('f-name').value     = p.name;
      document.getElementById('f-barcode').value  = p.barcode;
      document.getElementById('f-category').value = p.category;
      document.getElementById('f-price').value    = p.price;
      document.getElementById('f-cost').value     = p.cost;
      document.getElementById('f-unit').value     = p.unit;
      document.getElementById('f-low').value      = p.low_stock_threshold;
      document.getElementById('f-desc').value     = p.description || '';
      document.getElementById('f-featured').checked = p.is_featured;
      document.getElementById('pm-modal-title').textContent = 'Edit Product';
      document.getElementById('stock-init-group').style.display = 'none';
      openModal('product-modal');
    } catch (e) { showFlash(e.message, 'error'); }
  }

  async function saveProduct() {
    const id = document.getElementById('product-id').value;
    const payload = {
      name:                document.getElementById('f-name').value.trim(),
      barcode:             document.getElementById('f-barcode').value.trim(),
      category:            document.getElementById('f-category').value.trim(),
      price:               parseFloat(document.getElementById('f-price').value) || 0,
      cost:                parseFloat(document.getElementById('f-cost').value) || 0,
      unit:                document.getElementById('f-unit').value.trim(),
      description:         document.getElementById('f-desc').value.trim(),
      low_stock_threshold: parseFloat(document.getElementById('f-low').value) || 5,
      is_featured:         document.getElementById('f-featured').checked,
      stock:               parseFloat(document.getElementById('f-stock')?.value || 0) || 0,
    };
    if (!payload.name) { showFlash('Product name required', 'error'); return; }
    const btn = document.getElementById('save-product-btn');
    setLoading(btn, true, 'Saving…');
    try {
      if (id) {
        await api(`/api/inventory/product/${id}`, 'PUT', payload);
        showFlash('Product updated', 'success');
      } else {
        await api('/api/inventory/product', 'POST', payload);
        showFlash('Product added', 'success');
      }
      closeModal('product-modal');
      loadProducts(); loadAlerts();
    } catch (e) { showFlash(e.message, 'error'); }
    finally { setLoading(btn, false); }
  }

  async function deleteProduct(id, e) {
    e?.stopPropagation();
    if (!confirmAction('Soft-delete this product?')) return;
    try {
      await api(`/api/inventory/product/${id}`, 'DELETE');
      showFlash('Product removed', 'success');
      loadProducts(); loadAlerts();
    } catch (e) { showFlash(e.message, 'error'); }
  }

  function openAdjust(id) {
    document.getElementById('adjust-id').value     = id;
    document.getElementById('adjust-amount').value = '';
    document.getElementById('adjust-reason').value = '';
    openModal('adjust-modal');
  }

  async function saveAdjust() {
    const id     = document.getElementById('adjust-id').value;
    const amount = parseFloat(document.getElementById('adjust-amount').value);
    const reason = document.getElementById('adjust-reason').value.trim();
    if (isNaN(amount)) { showFlash('Enter a valid amount', 'error'); return; }
    const btn = document.getElementById('save-adjust-btn');
    setLoading(btn, true, 'Saving…');
    try {
      const data = await api('/api/stock-adjust', 'POST', { product_id: id, amount, reason });
      showFlash(`New qty: ${data.new_qty}`, 'success');
      closeModal('adjust-modal');
      loadProducts(); loadAlerts();
      if (currentId == id) selectProduct(id);
    } catch (e) { showFlash(e.message, 'error'); }
    finally { setLoading(btn, false); }
  }

  async function loadAlerts() {
    try {
      const data = await api('/api/stock-alerts');
      const el = document.getElementById('inv-alerts');
      if (!el) return;
      const all = [
        ...data.out_of_stock.map(i => ({ ...i, type: 'out' })),
        ...data.low_stock.map(i => ({ ...i, type: 'low' })),
      ];
      const badge = document.getElementById('alerts-count');
      if (badge) badge.textContent = all.length;
      if (!all.length) { el.innerHTML = '<div style="padding:10px;color:var(--text3);font-size:11px">✓ All stock levels OK</div>'; return; }
      el.innerHTML = all.map(i =>
        `<div class="alert-pill ${i.type}" onclick="INV.scrollTo(${i.id})">
          <span>${escHtml(i.name)}</span>
          <span class="pill-qty">${i.type === 'out' ? 'OUT' : i.stock + ' ' + (i.unit||'')}</span>
        </div>`).join('');
    } catch {}
  }

  function scrollTo(id) {
    const row = document.querySelector(`#inv-tbody tr[data-id="${id}"]`);
    const card = document.querySelector(`#inv-mobile-list .inv-mobile-card[data-id="${id}"]`);
    if (row) row.scrollIntoView({ behavior:'smooth', block:'center' });
    if (card) card.scrollIntoView({ behavior:'smooth', block:'center' });
    if (row || card) selectProduct(id);
  }

  async function submitImport() {
    const file = document.getElementById('import-file').files[0];
    if (!file) { showFlash('Select a CSV file', 'error'); return; }
    const fd = new FormData(); fd.append('file', file);
    const btn = document.getElementById('import-btn');
    setLoading(btn, true, 'Importing…');
    try {
      const data = await apiForm('/api/inventory/import', fd);
      document.getElementById('import-result').textContent = `✓ Added: ${data.added}  Skipped: ${data.skipped}  Errors: ${data.errors}`;
      loadProducts(); loadAlerts();
    } catch (e) { showFlash(e.message, 'error'); }
    finally { setLoading(btn, false); }
  }

  return { init, loadProducts, selectProduct, openAdd, openEdit, saveProduct, deleteProduct, openAdjust, saveAdjust, scrollTo, submitImport };
})();
