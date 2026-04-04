import os, threading, time
from flask import Flask, redirect, url_for
from flask_wtf.csrf import CSRFProtect
from models import db, login_manager
from config import config

def _auto_backup_worker(app):
    """Background thread: creates a backup every 24 hours if auto_backup enabled."""
    time.sleep(60)  # Wait 1 min after startup
    while True:
        try:
            with app.app_context():
                from models.helpers import get_setting
                if get_setting('auto_backup', '0') == '1':
                    from models.audit import Backup
                    from models.helpers import audit
                    import zipfile, datetime, pytz
                    bdir = get_setting('backup_path', 'backups')
                    if not os.path.isabs(bdir):
                        bdir = os.path.join(app.root_path, bdir)
                    os.makedirs(bdir, exist_ok=True)
                    ts    = datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                    fname = f'auto_backup_{ts}.zip'
                    fpath = os.path.join(bdir, fname)
                    db_url = app.config['SQLALCHEMY_DATABASE_URI']
                    with zipfile.ZipFile(fpath, 'w', zipfile.ZIP_DEFLATED) as zf:
                        zf.writestr('MANIFEST.txt', f'Auto Backup\nCreated:{ts}\n')
                    size = os.path.getsize(fpath)
                    b = Backup(filename=fname, path=fpath, size_bytes=size, notes='Auto backup')
                    db.session.add(b)
                    db.session.commit()
                    audit('BACKUP_AUTO', f'Auto backup: {fname}')
        except Exception as e:
            pass
        time.sleep(86400)  # Sleep 24 hours

csrf = CSRFProtect()


def create_app(env='default'):
    app = Flask(__name__)
    app.config.from_object(config[env])

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from routes.auth       import auth_bp
    from routes.pos        import pos_bp
    from routes.inventory  import inv_bp
    from routes.reports    import rep_bp
    from routes.users      import users_bp
    from routes.settings   import settings_bp
    from routes.backups    import backup_bp
    from routes.audit_route import audit_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(pos_bp)
    app.register_blueprint(inv_bp)
    app.register_blueprint(rep_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(backup_bp)
    app.register_blueprint(audit_bp)

    # Exempt JSON API routes from CSRF (session-protected)
    with app.app_context():
        for rule in list(app.url_map.iter_rules()):
            if rule.rule.startswith('/api/'):
                view = app.view_functions.get(rule.endpoint)
                if view:
                    csrf.exempt(view)

    @app.route('/')
    def index():
        return redirect(url_for('pos.pos'))

    # Start auto-backup background thread
    if not app.config.get('TESTING'):
        t = threading.Thread(target=_auto_backup_worker, args=(app,), daemon=True)
        t.start()

    with app.app_context():
        db.create_all()
        _seed_defaults()

    return app


def _seed_defaults():
    from models.helpers import ensure_settings
    from models.sale import PaymentMethod
    from models.product import Category

    ensure_settings()

    default_pms = [
        ('cash',       'Cash',               '💵', 0, True),
        ('mpesa',      'M-Pesa',             '📱', 1, True),
        ('paybill',    'Paybill',            '🏦', 2, True),
        ('till',       'Till Number',        '🔢', 3, True),
        ('send_money', 'Send Money',         '💸', 4, False),
        ('pochi',      'Pochi La Biashara',  '🛒', 5, False),
        ('card',       'Card',               '💳', 6, False),
        ('credit',     'Credit',             '📋', 7, False),
    ]
    for name, label, icon, sort, active in default_pms:
        if not PaymentMethod.query.filter_by(name=name).first():
            db.session.add(PaymentMethod(
                name=name, label=label, icon=icon,
                sort_order=sort, is_active=active
            ))

    default_cats = [
        ('Flour & Grains',    '🌾', '#F0883E'),
        ('Beverages',         '🥤', '#58A6FF'),
        ('Dairy',             '🥛', '#3FB950'),
        ('Cooking Oils',      '🫙', '#D29922'),
        ('Spices & Seasoning','🌶️', '#FF6B6B'),
        ('Cleaning',          '🧼', '#BC8CFF'),
        ('Personal Care',     '🧴', '#FF9F43'),
        ('Snacks & Biscuits', '🍫', '#F368E0'),
        ('Fresh Produce',     '🥦', '#10AC84'),
        ('Meat & Protein',    '🥩', '#EE5A24'),
        ('General',           '📦', '#8B949E'),
    ]
    for name, icon, color in default_cats:
        if not Category.query.filter_by(name=name).first():
            db.session.add(Category(name=name, icon=icon, color=color))

    db.session.commit()


app = create_app(os.environ.get('FLASK_ENV', 'default'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
