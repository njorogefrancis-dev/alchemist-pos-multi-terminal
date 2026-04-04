import uuid
from datetime import datetime, timezone
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from models import db
from models.product import Product, Inventory, Category
from models.sale import Sale, SaleItem, PaymentMethod
from models.helpers import audit, get_setting
import os, anthropic

pos_bp = Blueprint('pos', __name__)


def _settings():
    return {
        'currency_symbol':    get_setting('currency_symbol', 'KSh'),
        'tax_rate':           float(get_setting('tax_rate', '16')),
        'tax_name':           get_setting('tax_name', 'VAT'),
        'tax_inclusive':      get_setting('tax_inclusive', '1') == '1',
        'max_discount_pct':   float(get_setting('max_discount_pct', '100')),
        'track_stock':        get_setting('track_stock', '1') == '1',
        'allow_negative_stock': get_setting('allow_negative_stock', '0') == '1',
        'paybill_number':     get_setting('paybill_number', ''),
        'till_number':        get_setting('till_number', ''),
        'send_money_name':    get_setting('send_money_name', ''),
        'pochi_number':       get_setting('pochi_number', ''),
        'shop_name':          get_setting('shop_name', 'AlchemyPOS'),
        'shop_address':       get_setting('shop_address', ''),
        'shop_phone':         get_setting('shop_phone', ''),
        'receipt_header':     get_setting('receipt_header', ''),
        'receipt_footer':     get_setting('receipt_footer', ''),
        'show_tax':           get_setting('show_tax_on_receipt', '1') == '1',
        'ai_enabled':         get_setting('ai_enabled', '1') == '1',
    }


@pos_bp.route('/pos')
@login_required
def pos():
    cats = Category.query.order_by(Category.name).all()
    pms  = PaymentMethod.query.filter_by(is_active=True).order_by(PaymentMethod.sort_order).all()
    return render_template('pos.html', categories=cats, payment_methods=pms, settings=_settings())


@pos_bp.route('/api/products')
@login_required
def api_products():
    q   = request.args.get('q', '').strip()
    cat = request.args.get('cat', '').strip()
    track = get_setting('track_stock', '1') == '1'
    qry = Product.query.filter_by(is_active=True)
    if cat and cat != 'All':
        qry = qry.filter_by(category=cat)
    if q:
        qry = qry.filter(
            db.or_(Product.name.ilike(f'%{q}%'), Product.barcode.ilike(f'%{q}%'))
        )
    products = qry.order_by(Product.is_featured.desc(), Product.name).limit(120).all()
    out = []
    for p in products:
        qty = p.stock()
        # Always hide out-of-stock items from POS
        if qty <= 0:
            continue
        out.append({
            'id': p.id, 'name': p.name, 'category': p.category,
            'price': p.price_float(), 'stock': qty, 'unit': p.unit,
            'barcode': p.barcode, 'is_featured': p.is_featured,
            'is_low': p.is_low_stock(),
        })
    return jsonify(out)


@pos_bp.route('/api/stock-alerts')
@login_required
def api_stock_alerts():
    products = Product.query.filter_by(is_active=True).join(Inventory).all()
    out_list, low_list = [], []
    for p in products:
        inv = p.inventory
        if not inv: continue
        qty = float(inv.quantity)
        thresh = float(inv.low_stock_threshold)
        if qty <= 0:
            out_list.append({'id': p.id, 'name': p.name, 'stock': qty, 'unit': p.unit})
        elif qty <= thresh:
            low_list.append({'id': p.id, 'name': p.name, 'stock': qty, 'unit': p.unit, 'threshold': thresh})
    return jsonify({'out_of_stock': out_list, 'low_stock': low_list})


@pos_bp.route('/api/sale', methods=['POST'])
@login_required
def api_sale():
    data  = request.get_json() or {}
    items = data.get('items', [])
    if not items:
        return jsonify({'error': 'Cart is empty'}), 400

    track     = get_setting('track_stock', '1') == '1'
    allow_neg = get_setting('allow_negative_stock', '0') == '1'
    tax_rate  = float(get_setting('tax_rate', '16'))
    tax_inc   = get_setting('tax_inclusive', '1') == '1'
    discount  = float(data.get('discount', 0))
    method    = data.get('payment_method', 'cash')
    tendered  = float(data.get('amount_tendered', 0))

    sale_items, subtotal = [], 0
    for item in items:
        pid   = item.get('product_id')
        qty   = float(item.get('qty', 1))
        price = float(item.get('price', 0))
        name  = item.get('name', '')
        if pid:
            p = db.session.get(Product, pid)
            if not p or not p.is_active:
                return jsonify({'error': f'Product not found: {name}'}), 400
            if track:
                inv = p.inventory
                if not inv or (float(inv.quantity) < qty and not allow_neg):
                    return jsonify({'error': f'Insufficient stock: {name}'}), 400
            sale_items.append({'product': p, 'qty': qty, 'price': price, 'name': p.name})
        else:
            sale_items.append({'product': None, 'qty': qty, 'price': price, 'name': name})
        subtotal += qty * price

    after = max(0, subtotal - discount)
    if tax_inc:
        tax   = round(after - after / (1 + tax_rate / 100), 2)
        total = round(after, 2)
    else:
        tax   = round(after * tax_rate / 100, 2)
        total = round(after + tax, 2)
    change = round(tendered - total, 2)

    rcpt = f"RCP{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}{str(uuid.uuid4())[:4].upper()}"
    sale = Sale(
        receipt_number=rcpt, cashier_id=current_user.id,
        subtotal=round(subtotal,2), discount=round(discount,2),
        tax=tax, total=total, payment_method=method,
        amount_tendered=tendered, change_given=max(0, change),
    )
    db.session.add(sale); db.session.flush()
    for si in sale_items:
        db.session.add(SaleItem(
            sale_id=sale.id,
            product_id=si['product'].id if si['product'] else None,
            product_name=si['name'], quantity=si['qty'],
            unit_price=si['price'], subtotal=round(si['qty']*si['price'],2),
        ))
        if track and si['product']:
            inv = si['product'].inventory
            if inv:
                inv.quantity = float(inv.quantity) - si['qty']
                inv.last_updated = datetime.now(timezone.utc)
    db.session.commit()
    audit('SALE', f'{rcpt} total={total} method={method}')

    sym = get_setting('currency_symbol', 'KSh')
    return jsonify({'success': True, 'receipt': {
        'receipt_number': rcpt,
        'date': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
        'cashier': current_user.full_name or current_user.username,
        'items': [{'name':si['name'],'qty':si['qty'],'price':si['price'],'subtotal':round(si['qty']*si['price'],2)} for si in sale_items],
        'subtotal': subtotal, 'discount': discount, 'tax': tax, 'total': total,
        'payment_method': method, 'amount_tendered': tendered, 'change': max(0,change),
        'currency': sym,
        'shop_name': get_setting('shop_name','AlchemyPOS'),
        'shop_address': get_setting('shop_address',''),
        'shop_phone': get_setting('shop_phone',''),
        'receipt_header': get_setting('receipt_header',''),
        'receipt_footer': get_setting('receipt_footer',''),
        'show_tax': get_setting('show_tax_on_receipt','1') == '1',
        'tax_name': get_setting('tax_name','VAT'),
    }})


@pos_bp.route('/api/ai/search', methods=['POST'])
@login_required
def api_ai_search():
    """AI-powered natural language product search using Claude."""
    if get_setting('ai_enabled', '1') != '1':
        return jsonify({'error': 'AI disabled'}), 400
    data  = request.get_json() or {}
    query = data.get('query', '').strip()
    if not query:
        return jsonify({'results': []})

    # Get product catalog for context
    products = Product.query.filter_by(is_active=True).join(Inventory).limit(300).all()
    catalog  = [{'id': p.id, 'name': p.name, 'category': p.category,
                 'price': p.price_float(), 'stock': p.stock()} for p in products]

    api_key = get_setting('anthropic_api_key','') or os.environ.get('ANTHROPIC_API_KEY','')
    if not api_key:
        # Fallback to simple text search
        q = query.lower()
        results = [p for p in catalog if q in p['name'].lower() or q in p['category'].lower()]
        return jsonify({'results': results[:20], 'ai': False})

    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model='claude-sonnet-4-5',
            max_tokens=512,
            system="""You are a smart product search assistant for a Kenyan retail POS system.
Given a natural language query and a product catalog, return the IDs of matching products as JSON.
Return ONLY a JSON array of product IDs like: [1, 5, 12]
Match semantically — e.g. "uji" → maize/millet flour, "ngano" → wheat flour, "sabuni" → soap.
Return up to 20 best matches. If nothing matches return [].""",
            messages=[{
                'role': 'user',
                'content': f'Query: "{query}"\n\nCatalog: {str(catalog[:200])}'
            }]
        )
        import json, re
        text = msg.content[0].text.strip()
        ids = json.loads(re.search(r'\[[\d,\s]*\]', text).group())
        id_set = set(ids)
        matched = [p for p in catalog if p['id'] in id_set]
        return jsonify({'results': matched, 'ai': True})
    except Exception as e:
        # Fallback
        q = query.lower()
        results = [p for p in catalog if q in p['name'].lower() or q in p['category'].lower()]
        return jsonify({'results': results[:20], 'ai': False, 'error': str(e)})


@pos_bp.route('/api/ai/suggest', methods=['POST'])
@login_required
def api_ai_suggest():
    """AI-powered upsell suggestions based on current cart."""
    if get_setting('ai_enabled', '1') != '1':
        return jsonify({'suggestions': []})
    data      = request.get_json() or {}
    cart_items = data.get('cart', [])
    if not cart_items:
        return jsonify({'suggestions': []})

    api_key = get_setting('anthropic_api_key','') or os.environ.get('ANTHROPIC_API_KEY','')
    if not api_key:
        return jsonify({'suggestions': []})

    products = Product.query.filter_by(is_active=True).join(Inventory).limit(200).all()
    catalog  = [{'id':p.id,'name':p.name,'category':p.category,'price':p.price_float()} for p in products
                if p.stock() > 0]
    cart_names = [i.get('name','') for i in cart_items]

    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=256,
            system="""You are a smart retail upsell assistant for a Kenyan shop.
Given items already in the cart, suggest 3-5 complementary products from the catalog.
Return ONLY a JSON array of product IDs like: [4, 17, 23]
Think: if they have bread → suggest butter/jam/milk. Unga → cooking oil/salt. Chicken → spices/cooking oil.""",
            messages=[{
                'role': 'user',
                'content': f'Cart: {cart_names}\nCatalog: {str(catalog[:150])}'
            }]
        )
        import json, re
        text = msg.content[0].text.strip()
        ids  = json.loads(re.search(r'\[[\d,\s]*\]', text).group())
        cart_ids = {i.get('product_id') for i in cart_items}
        matched  = [p for p in catalog if p['id'] in set(ids) and p['id'] not in cart_ids]
        return jsonify({'suggestions': matched[:5]})
    except Exception:
        return jsonify({'suggestions': []})
