from models import db
from models.audit import AuditLog, Setting
from flask import request as _req

DEFAULT_SETTINGS = {
    'shop_name': 'AlchemyPOS',
    'shop_address': 'Nairobi, Kenya',
    'shop_phone': '',
    'shop_email': '',
    'paybill_number': '',
    'till_number': '',
    'send_money_name': '',
    'pochi_number': '',
    'receipt_header': 'Asante kwa kununua kwetu!',
    'receipt_footer': 'Bidhaa ziuzwazo hazirudi.',
    'show_tax_on_receipt': '1',
    'currency_symbol': 'KSh',
    'currency_name': 'Kenyan Shilling',
    'tax_rate': '16',
    'tax_name': 'VAT',
    'tax_inclusive': '1',
    'default_low_stock': '5',
    'default_unit': 'pcs',
    'track_stock': '1',
    'warn_out_of_stock': '1',
    'allow_negative_stock': '0',
    'auto_print_receipt': '0',
    'max_discount_pct': '100',
    'theme': 'dark',
    'printer_command': '',
    'backup_path': 'backups',
    'auto_backup': '0',
    'session_hours': '8',
    'ai_enabled': '1',
    'anthropic_api_key': '',
}


def get_setting(key, default=''):
    s = db.session.get(Setting, key)
    return s.value if s else default


def set_setting(key, value):
    s = db.session.get(Setting, key)
    if s:
        s.value = str(value)
    else:
        db.session.add(Setting(key=key, value=str(value)))
    db.session.commit()


def ensure_settings():
    for k, v in DEFAULT_SETTINGS.items():
        if not db.session.get(Setting, k):
            db.session.add(Setting(key=k, value=v))
    db.session.commit()


def audit(action, details='', user=None, username='system'):
    from flask_login import current_user
    uid, uname = None, username
    if user:
        uid, uname = user.id, user.username
    else:
        try:
            if current_user and current_user.is_authenticated:
                uid, uname = current_user.id, current_user.username
        except Exception:
            pass
    ip = ''
    try:
        ip = _req.remote_addr or ''
    except Exception:
        pass
    db.session.add(AuditLog(user_id=uid, username=uname, action=action, details=details, ip_address=ip))
    db.session.commit()
