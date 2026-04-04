from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from functools import wraps
from models.audit import AuditLog

audit_bp = Blueprint('audit', __name__)

def admin_required(f):
    @wraps(f)
    @login_required
    def d(*a,**kw):
        if current_user.role!='admin': flash('Access denied.','error'); return redirect(url_for('pos.pos'))
        return f(*a,**kw)
    return d

@audit_bp.route('/audit')
@admin_required
def audit_log():
    page=int(request.args.get('page',1)); per=50
    action_filter=request.args.get('action','')
    username_filter=request.args.get('username','')
    search=request.args.get('search','')
    q=AuditLog.query
    if action_filter: q=q.filter_by(action=action_filter)
    if username_filter: q=q.filter(AuditLog.username.ilike(f'%{username_filter}%'))
    if search: q=q.filter(AuditLog.details.ilike(f'%{search}%')|AuditLog.action.ilike(f'%{search}%'))
    q=q.order_by(AuditLog.created_at.desc())
    total=q.count()
    logs=q.offset((page-1)*per).limit(per).all()
    pages=(total+per-1)//per
    actions=[r[0] for r in AuditLog.query.with_entities(AuditLog.action).distinct().order_by(AuditLog.action).all()]
    return render_template('audit.html',logs=logs,page=page,pages=pages,total=total,
                           actions=actions,action_filter=action_filter,username_filter=username_filter,search=search)
