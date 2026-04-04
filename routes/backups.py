import os, shutil, zipfile
from datetime import datetime, timezone
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, send_file
from flask_login import login_required, current_user
from functools import wraps
from models import db
from models.audit import Backup
from models.helpers import audit, get_setting

backup_bp = Blueprint('backups', __name__)

def admin_required(f):
    @wraps(f)
    @login_required
    def d(*a,**kw):
        if current_user.role!='admin': flash('Access denied.','error'); return redirect(url_for('pos.pos'))
        return f(*a,**kw)
    return d

def _bdir():
    from flask import current_app
    p = get_setting('backup_path','backups')
    if not os.path.isabs(p): p = os.path.join(current_app.root_path, p)
    os.makedirs(p, exist_ok=True)
    return p

@backup_bp.route('/backups')
@admin_required
def backups():
    return render_template('backups.html', backups=Backup.query.order_by(Backup.created_at.desc()).all())

@backup_bp.route('/api/backups/create', methods=['POST'])
@admin_required
def api_create():
    from flask import current_app
    notes = (request.get_json() or {}).get('notes','')
    bdir  = _bdir()
    ts    = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    fname = f'backup_{ts}.zip'
    fpath = os.path.join(bdir, fname)
    db_url = current_app.config['SQLALCHEMY_DATABASE_URI']
    with zipfile.ZipFile(fpath,'w',zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('MANIFEST.txt', f'AlchemyPOS Backup\nCreated:{ts}\nBy:{current_user.username}\nNotes:{notes}\nDB:{db_url}\n')
    size = os.path.getsize(fpath)
    b = Backup(filename=fname, path=fpath, size_bytes=size, created_by=current_user.id, notes=notes)
    db.session.add(b); db.session.commit()
    audit('BACKUP_CREATE', fname)
    return jsonify({'success':True,'filename':fname,'size':size})

@backup_bp.route('/api/backups/<int:bid>/download')
@admin_required
def api_download(bid):
    b = db.session.get(Backup, bid)
    if not b or not os.path.exists(b.path): flash('Backup not found.','error'); return redirect(url_for('backups.backups'))
    return send_file(b.path, as_attachment=True, download_name=b.filename)

@backup_bp.route('/api/backups/<int:bid>/delete', methods=['DELETE'])
@admin_required
def api_delete(bid):
    b = db.session.get(Backup, bid)
    if not b: return jsonify({'error':'Not found'}), 404
    if os.path.exists(b.path): os.remove(b.path)
    db.session.delete(b); db.session.commit()
    audit('BACKUP_DELETE', b.filename)
    return jsonify({'success':True})
