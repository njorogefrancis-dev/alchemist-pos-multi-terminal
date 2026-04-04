import csv, io
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, Response
from flask_login import login_required, current_user
from datetime import datetime, timezone
from functools import wraps
from models import db
from models.product import Product, Inventory, Category
from models.helpers import audit, get_setting

inv_bp = Blueprint('inventory', __name__)

def inv_required(f):
    @wraps(f)
    def d(*a, **kw):
        if not current_user.is_authenticated:
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Unauthorized'}), 401
            return redirect(url_for('auth.login'))
        if current_user.role not in ('admin', 'inventory_manager'):
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Forbidden'}), 403
            flash('Access denied.', 'error')
            return redirect(url_for('pos.pos'))
        return f(*a, **kw)
    return d

@inv_bp.route('/inventory')
@inv_required
def inventory():
    cats = [c.name for c in Category.query.order_by(Category.name).all()]
    s = {'currency_symbol': get_setting('currency_symbol','KSh'),
         'default_unit': get_setting('default_unit','pcs'),
         'default_low_stock': get_setting('default_low_stock','5')}
    return render_template('inventory.html', categories=cats, settings=s)

@inv_bp.route('/api/inventory/products')
@inv_required
def api_products():
    q   = request.args.get('q','').strip()
    cat = request.args.get('cat','').strip()
    qry = Product.query.filter_by(is_active=True)
    if cat and cat != 'All': qry = qry.filter_by(category=cat)
    if q: qry = qry.filter(db.or_(Product.name.ilike(f'%{q}%'), Product.barcode.ilike(f'%{q}%')))
    products = qry.order_by(Product.name).all()
    return jsonify([{
        'id':p.id,'barcode':p.barcode,'name':p.name,'category':p.category,
        'price':p.price_float(),'cost':p.cost_float(),'unit':p.unit,
        'stock': float(p.inventory.quantity) if p.inventory else 0,
        'low_stock_threshold': float(p.inventory.low_stock_threshold) if p.inventory else 5,
        'margin': p.margin_pct(), 'is_featured': p.is_featured,
    } for p in products])

@inv_bp.route('/api/inventory/product/<int:pid>')
@inv_required
def api_product(pid):
    p = db.session.get(Product, pid)
    if not p or not p.is_active: return jsonify({'error':'Not found'}), 404
    inv = p.inventory
    return jsonify({
        'id':p.id,'barcode':p.barcode,'name':p.name,'category':p.category,
        'price':p.price_float(),'cost':p.cost_float(),'unit':p.unit,'description':p.description,
        'stock': float(inv.quantity) if inv else 0,
        'low_stock_threshold': float(inv.low_stock_threshold) if inv else 5,
        'margin': p.margin_pct(), 'is_featured': p.is_featured,
        'created_at': p.created_at.strftime('%Y-%m-%d') if p.created_at else '',
        'updated_at': p.updated_at.strftime('%Y-%m-%d') if p.updated_at else '',
    })

@inv_bp.route('/api/inventory/product', methods=['POST'])
@inv_required
def api_add_product():
    d = request.get_json() or {}
    name = d.get('name','').strip()
    if not name: return jsonify({'error':'Name required'}), 400
    cat = d.get('category','General').strip() or 'General'
    if not Category.query.filter_by(name=cat).first():
        db.session.add(Category(name=cat)); db.session.flush()
    p = Product(barcode=d.get('barcode',''), name=name, category=cat,
                price=float(d.get('price',0)), cost=float(d.get('cost',0)),
                unit=d.get('unit', get_setting('default_unit','pcs')),
                description=d.get('description',''), is_featured=bool(d.get('is_featured',False)))
    db.session.add(p); db.session.flush()
    thresh = float(d.get('low_stock_threshold', get_setting('default_low_stock','5')))
    db.session.add(Inventory(product_id=p.id, quantity=float(d.get('stock',0)), low_stock_threshold=thresh))
    db.session.commit()
    audit('PRODUCT_ADD', f'Added: {name}')
    return jsonify({'success':True,'id':p.id})

@inv_bp.route('/api/inventory/product/<int:pid>', methods=['PUT'])
@inv_required
def api_edit_product(pid):
    p = db.session.get(Product, pid)
    if not p or not p.is_active: return jsonify({'error':'Not found'}), 404
    d = request.get_json() or {}
    name = d.get('name', p.name).strip()
    if not name: return jsonify({'error':'Name required'}), 400
    cat = d.get('category', p.category).strip() or 'General'
    if not Category.query.filter_by(name=cat).first():
        db.session.add(Category(name=cat)); db.session.flush()
    p.name=name; p.barcode=d.get('barcode',p.barcode); p.category=cat
    p.price=float(d.get('price',p.price)); p.cost=float(d.get('cost',p.cost))
    p.unit=d.get('unit',p.unit); p.description=d.get('description',p.description)
    p.is_featured=bool(d.get('is_featured',p.is_featured))
    p.updated_at=datetime.now(timezone.utc)
    if p.inventory:
        p.inventory.low_stock_threshold=float(d.get('low_stock_threshold', p.inventory.low_stock_threshold))
    db.session.commit()
    audit('PRODUCT_EDIT', f'Edited: {name}')
    return jsonify({'success':True})

@inv_bp.route('/api/inventory/product/<int:pid>', methods=['DELETE'])
@inv_required
def api_delete_product(pid):
    p = db.session.get(Product, pid)
    if not p: return jsonify({'error':'Not found'}), 404
    p.is_active=False; db.session.commit()
    audit('PRODUCT_DELETE', f'Deleted: {p.name}')
    return jsonify({'success':True})

@inv_bp.route('/api/stock-adjust', methods=['POST'])
@inv_required
def api_stock_adjust():
    d = request.get_json() or {}
    p = db.session.get(Product, d.get('product_id'))
    if not p or not p.is_active: return jsonify({'error':'Not found'}), 404
    inv = p.inventory
    if not inv:
        inv = Inventory(product_id=p.id, quantity=0, low_stock_threshold=5)
        db.session.add(inv)
    old = float(inv.quantity)
    inv.quantity = old + float(d.get('amount',0))
    inv.last_updated = datetime.now(timezone.utc)
    db.session.commit()
    audit('STOCK_ADJUST', f'{p.name}: {old} → {float(inv.quantity)} ({d.get("reason","")})')
    return jsonify({'success':True,'new_qty': float(inv.quantity)})

@inv_bp.route('/api/inventory/import', methods=['POST'])
@inv_required
def api_import():
    f = request.files.get('file')
    if not f: return jsonify({'error':'No file'}), 400
    stream = io.StringIO(f.stream.read().decode('utf-8-sig'))
    reader = csv.DictReader(stream)
    added=skipped=errors=0
    for row in reader:
        try:
            name = row.get('name','').strip()
            if not name: skipped+=1; continue
            cat = row.get('category','General').strip() or 'General'
            if not Category.query.filter_by(name=cat).first():
                db.session.add(Category(name=cat)); db.session.flush()
            p = Product(barcode=row.get('barcode',''), name=name, category=cat,
                        price=float(row.get('price',0) or 0), cost=float(row.get('cost',0) or 0),
                        unit=row.get('unit','pcs'))
            db.session.add(p); db.session.flush()
            db.session.add(Inventory(product_id=p.id,
                quantity=float(row.get('stock',0) or 0),
                low_stock_threshold=float(row.get('low_stock_threshold',5) or 5)))
            added+=1
        except Exception: errors+=1
    db.session.commit()
    audit('CSV_IMPORT', f'added={added} skipped={skipped} errors={errors}')
    return jsonify({'success':True,'added':added,'skipped':skipped,'errors':errors})

@inv_bp.route('/api/inventory/export')
@inv_required
def api_export():
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(['name','barcode','category','price','cost','unit','stock','low_stock_threshold'])
    for p in products:
        inv = p.inventory
        w.writerow([p.name,p.barcode,p.category,p.price_float(),p.cost_float(),p.unit,
                    float(inv.quantity) if inv else 0, float(inv.low_stock_threshold) if inv else 5])
    out.seek(0)
    return Response(out.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition':'attachment;filename=inventory.csv'})

@inv_bp.route('/api/inventory/sample-csv')
@inv_required
def api_sample():
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(['name','barcode','category','price','cost','unit','stock','low_stock_threshold'])
    w.writerow(['Unga wa Dume 2kg','6001001','Flour & Grains','185','140','bag','80','10'])
    w.writerow(['Brookside Milk 1L','6001002','Dairy','120','92','packet','60','15'])
    out.seek(0)
    return Response(out.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition':'attachment;filename=sample_import.csv'})

@inv_bp.route('/api/category', methods=['POST'])
@inv_required
def api_add_category():
    d = request.get_json()
    name = d.get('name','').strip()
    if not name: return jsonify({'error':'Name required'}), 400
    if Category.query.filter_by(name=name).first(): return jsonify({'error':'Already exists'}), 400
    c = Category(name=name, description=d.get('description',''), icon=d.get('icon','📦'), color=d.get('color','#F0883E'))
    db.session.add(c); db.session.commit()
    audit('CATEGORY_ADD', f'Category: {name}')
    return jsonify({'success':True,'id':c.id,'name':c.name})

@inv_bp.route('/api/category/<int:cid>', methods=['DELETE'])
@inv_required
def api_delete_category(cid):
    c = db.session.get(Category, cid)
    if not c: return jsonify({'error':'Not found'}), 404
    if c.name == 'General':
        return jsonify({'error':'Default category cannot be deleted'}), 400
    fallback = Category.query.filter_by(name='General').first()
    if not fallback:
        fallback = Category(name='General', icon='📦', color='#F0883E')
        db.session.add(fallback)
        db.session.flush()
    affected = Product.query.filter_by(category=c.name, is_active=True).all()
    for p in affected:
        p.category = fallback.name
    name = c.name
    moved = len(affected)
    db.session.delete(c)
    db.session.commit()
    audit('CATEGORY_DELETE', f'Category: {name} (moved_products={moved})')
    return jsonify({'success':True, 'moved_products': moved})
