from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from functools import wraps
from models import db
from models.product import Category
from models.sale import PaymentMethod
from models.helpers import audit, get_setting, set_setting, DEFAULT_SETTINGS

settings_bp = Blueprint('settings', __name__)

def admin_required(f):
    @wraps(f)
    @login_required
    def d(*a,**kw):
        if current_user.role!='admin': flash('Access denied.','error'); return redirect(url_for('pos.pos'))
        return f(*a,**kw)
    return d

@settings_bp.route('/settings', methods=['GET','POST'])
@admin_required
def settings():
    if request.method == 'POST':
        text_keys = ['shop_name','shop_address','shop_phone','shop_email','theme',
                     'paybill_number','till_number','send_money_name','pochi_number',
                     'receipt_header','receipt_footer','currency_symbol','currency_name',
                     'tax_rate','tax_name','default_low_stock','default_unit',
                     'max_discount_pct','printer_command','backup_path','anthropic_api_key']
        bool_keys = ['show_tax_on_receipt','tax_inclusive','track_stock','warn_out_of_stock',
                     'allow_negative_stock','auto_print_receipt','auto_backup','ai_enabled']
        for k in text_keys:
            val = request.form.get(k, None)
            if val is not None:  # Only save if field was in the form
                set_setting(k, val.strip())
        for k in bool_keys: set_setting(k, '1' if request.form.get(k) else '0')
        for pm in PaymentMethod.query.all():
            pm.is_active = bool(request.form.get(f'pm_{pm.name}'))
        db.session.commit()
        new_pw = request.form.get('new_password','')
        if new_pw:
            if new_pw != request.form.get('confirm_password',''):
                flash('Passwords do not match.','error')
            elif len(new_pw)<6:
                flash('Password too short.','error')
            else:
                current_user.set_password(new_pw); db.session.commit()
                flash('Password updated.','success')
        audit('SETTINGS_SAVE','Settings updated')
        flash('Settings saved successfully.','success')
        from flask import make_response
        resp = make_response(redirect(url_for('settings.settings')))
        resp.set_cookie('theme', request.form.get('theme','dark'), max_age=31536000)
        return resp
    all_settings = {k: get_setting(k,v) for k,v in DEFAULT_SETTINGS.items()}
    cats = Category.query.order_by(Category.name).all()
    pms  = PaymentMethod.query.order_by(PaymentMethod.sort_order).all()
    return render_template('settings.html', s=all_settings, categories=cats, payment_methods=pms)
