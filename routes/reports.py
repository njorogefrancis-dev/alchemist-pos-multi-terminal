import csv, io
from flask import Blueprint, render_template, request, jsonify, Response, redirect, url_for, flash
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime, timezone, timedelta
from sqlalchemy import func
from models import db
from models.sale import Sale, SaleItem
from models.product import Product
from models.user import User
from models.helpers import get_setting, audit
import os, anthropic

rep_bp = Blueprint('reports', __name__)

def admin_required(f):
    @wraps(f)
    @login_required
    def d(*a, **kw):
        if current_user.role != 'admin':
            if request.path.startswith('/api/'):
                return jsonify({'error':'Forbidden'}), 403
            flash('Access denied.', 'error'); return redirect(url_for('pos.pos'))
        return f(*a, **kw)
    return d

def _filters():
    df = request.args.get('date_from','')
    dt = request.args.get('date_to','')
    cid = request.args.get('cashier_id','')
    pm  = request.args.get('payment_method','')
    s   = request.args.get('search','')
    quick = request.args.get('quick','')
    today = datetime.now(timezone.utc).date()
    if quick == 'today':   df = dt = str(today)
    elif quick == 'week':  df = str(today - timedelta(days=today.weekday())); dt = str(today)
    elif quick == 'month': df = str(today.replace(day=1)); dt = str(today)
    elif quick == 'year':  df = str(today.replace(month=1,day=1)); dt = str(today)
    return df, dt, cid, pm, s

def _base_q(df,dt,cid,pm,s):
    q = Sale.query.filter_by(status='completed')
    if df:
        try: q = q.filter(Sale.created_at >= datetime.strptime(df,'%Y-%m-%d'))
        except: pass
    if dt:
        try: q = q.filter(Sale.created_at < datetime.strptime(dt,'%Y-%m-%d') + timedelta(days=1))
        except: pass
    if cid: q = q.filter_by(cashier_id=cid)
    if pm:  q = q.filter_by(payment_method=pm)
    if s:   q = q.filter(Sale.receipt_number.ilike(f'%{s}%'))
    return q

@rep_bp.route('/reports')
@admin_required
def reports():
    cashiers = User.query.filter_by(is_active=True).order_by(User.username).all()
    return render_template('reports.html', cashiers=cashiers, currency=get_setting('currency_symbol','KSh'))

@rep_bp.route('/api/reports/summary')
@admin_required
def api_summary():
    df,dt,cid,pm,s = _filters()
    sales = _base_q(df,dt,cid,pm,s).all()
    if not sales:
        return jsonify({'transactions':0,'revenue':0,'discounts':0,'avg_sale':0,'tax':0,'profit':0,'currency':get_setting('currency_symbol','KSh')})
    revenue   = sum(float(x.total) for x in sales)
    discounts = sum(float(x.discount) for x in sales)
    tax       = sum(float(x.tax) for x in sales)
    sale_ids  = [x.id for x in sales]
    items     = SaleItem.query.filter(SaleItem.sale_id.in_(sale_ids)).all()
    cogs = 0
    for item in items:
        if item.product_id:
            p = db.session.get(Product, item.product_id)
            if p: cogs += float(p.cost) * float(item.quantity)
    return jsonify({'transactions':len(sales),'revenue':round(revenue,2),'discounts':round(discounts,2),
                    'avg_sale':round(revenue/len(sales),2),'tax':round(tax,2),
                    'profit':round(revenue-cogs,2),'currency':get_setting('currency_symbol','KSh')})

@rep_bp.route('/api/reports/sales')
@admin_required
def api_sales():
    df,dt,cid,pm,s = _filters()
    page = int(request.args.get('page',1)); per = 50
    q    = _base_q(df,dt,cid,pm,s).order_by(Sale.created_at.desc())
    total = q.count()
    sales = q.offset((page-1)*per).limit(per).all()
    sym   = get_setting('currency_symbol','KSh')
    return jsonify({'sales':[{
        'id':x.id,'receipt_number':x.receipt_number,
        'date':x.created_at.strftime('%Y-%m-%d %H:%M'),
        'cashier': x.cashier.full_name or x.cashier.username if x.cashier else 'Unknown',
        'payment_method':x.payment_method,'total':float(x.total),'currency':sym,
    } for x in sales], 'total':total, 'pages':(total+per-1)//per, 'page':page})

@rep_bp.route('/api/reports/sale/<int:sid>')
@admin_required
def api_sale_detail(sid):
    sale = db.session.get(Sale, sid)
    if not sale: return jsonify({'error':'Not found'}), 404
    sym = get_setting('currency_symbol','KSh')
    return jsonify({'receipt_number':sale.receipt_number,
        'date':sale.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        'cashier': sale.cashier.full_name or sale.cashier.username if sale.cashier else 'Unknown',
        'payment_method':sale.payment_method,
        'subtotal':float(sale.subtotal),'discount':float(sale.discount),
        'tax':float(sale.tax),'total':float(sale.total),
        'amount_tendered':float(sale.amount_tendered),'change_given':float(sale.change_given),
        'currency':sym,
        'items':[{'name':i.product_name,'qty':float(i.quantity),'price':float(i.unit_price),'subtotal':float(i.subtotal)} for i in sale.items]})

@rep_bp.route('/api/reports/top-products')
@admin_required
def api_top_products():
    df,dt,cid,pm,s = _filters()
    ids = [x.id for x in _base_q(df,dt,cid,pm,s).all()]
    if not ids: return jsonify([])
    rows = db.session.query(SaleItem.product_name,
        func.sum(SaleItem.quantity).label('qty'),
        func.sum(SaleItem.subtotal).label('revenue')
    ).filter(SaleItem.sale_id.in_(ids)).group_by(SaleItem.product_name).order_by(func.sum(SaleItem.quantity).desc()).limit(20).all()
    return jsonify([{'name':r.product_name,'qty':float(r.qty),'revenue':round(float(r.revenue),2)} for r in rows])

@rep_bp.route('/api/reports/payment-split')
@admin_required
def api_payment_split():
    df,dt,cid,pm,s = _filters()
    sales = _base_q(df,dt,cid,pm,s).all()
    split = {}
    for sale in sales:
        m = sale.payment_method
        if m not in split: split[m]={'method':m,'count':0,'total':0}
        split[m]['count']+=1; split[m]['total']+=float(sale.total)
    return jsonify([{'method':v['method'],'count':v['count'],'total':round(v['total'],2)} for v in split.values()])

@rep_bp.route('/api/reports/by-cashier')
@admin_required
def api_by_cashier():
    df,dt,cid,pm,s = _filters()
    sales = _base_q(df,dt,cid,pm,s).all()
    by_c = {}
    for sale in sales:
        uid = sale.cashier_id
        if uid not in by_c:
            name = sale.cashier.full_name or sale.cashier.username if sale.cashier else 'Unknown'
            by_c[uid]={'name':name,'transactions':0,'revenue':0}
        by_c[uid]['transactions']+=1; by_c[uid]['revenue']+=float(sale.total)
    return jsonify([{'name':v['name'],'transactions':v['transactions'],'revenue':round(v['revenue'],2)} for v in by_c.values()])

@rep_bp.route('/api/reports/hourly')
@admin_required
def api_hourly():
    """Hourly sales breakdown for chart."""
    df,dt,cid,pm,s = _filters()
    sales = _base_q(df,dt,cid,pm,s).all()
    hourly = [0]*24
    for sale in sales:
        h = sale.created_at.hour
        hourly[h] += float(sale.total)
    return jsonify([{'hour':h,'revenue':round(hourly[h],2)} for h in range(24)])

@rep_bp.route('/api/reports/ai-summary', methods=['POST'])
@admin_required
def api_ai_summary():
    """AI-generated natural language business summary."""
    api_key = get_setting('anthropic_api_key','') or os.environ.get('ANTHROPIC_API_KEY','')
    if not api_key: return jsonify({'summary':'AI not configured. Add your Anthropic API key in Settings.'})
    df,dt,cid,pm,s = _filters()
    sales = _base_q(df,dt,cid,pm,s).all()
    if not sales: return jsonify({'summary':'No sales data for the selected period.'})
    revenue   = round(sum(float(x.total) for x in sales),2)
    discounts = round(sum(float(x.discount) for x in sales),2)
    sym = get_setting('currency_symbol','KSh')
    ids = [x.id for x in sales]
    top = db.session.query(SaleItem.product_name, func.sum(SaleItem.quantity).label('qty')
          ).filter(SaleItem.sale_id.in_(ids)).group_by(SaleItem.product_name
          ).order_by(func.sum(SaleItem.quantity).desc()).limit(5).all()
    top_str = ', '.join(f'{r.product_name} ({float(r.qty):.0f})' for r in top)
    split = {}
    for sale in sales:
        m = sale.payment_method
        split[m] = split.get(m,0) + 1
    split_str = ', '.join(f'{k}:{v}' for k,v in split.items())
    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model='claude-sonnet-4-5',
            max_tokens=400,
            system='You are a helpful business analyst for a Kenyan retail shop. Write concise, actionable insights in 3-4 sentences. Be specific and positive but honest.',
            messages=[{'role':'user','content':
                f'Sales period: {df or "all time"} to {dt or "now"}\n'
                f'Transactions: {len(sales)}\nRevenue: {sym} {revenue}\nDiscounts: {sym} {discounts}\n'
                f'Top products: {top_str}\nPayment methods: {split_str}\n\nProvide a brief business summary and one actionable recommendation.'}]
        )
        return jsonify({'summary': msg.content[0].text})
    except Exception as e:
        return jsonify({'summary': f'AI unavailable: {str(e)}'})

@rep_bp.route('/api/reports/export/csv')
@admin_required
def export_csv():
    df,dt,cid,pm,s = _filters()
    sales = _base_q(df,dt,cid,pm,s).order_by(Sale.created_at.desc()).all()
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(['Receipt','Date','Cashier','Method','Subtotal','Discount','Tax','Total'])
    for sale in sales:
        cashier = sale.cashier.full_name or sale.cashier.username if sale.cashier else 'Unknown'
        w.writerow([sale.receipt_number,sale.created_at.strftime('%Y-%m-%d %H:%M'),cashier,
                    sale.payment_method,float(sale.subtotal),float(sale.discount),float(sale.tax),float(sale.total)])
    out.seek(0)
    return Response(out.getvalue(), mimetype='text/csv', headers={'Content-Disposition':'attachment;filename=sales_report.csv'})
