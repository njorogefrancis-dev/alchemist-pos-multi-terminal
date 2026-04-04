# routes/users.py
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from functools import wraps
from models import db
from models.user import User
from models.helpers import audit

users_bp = Blueprint('users', __name__)

def admin_required(f):
    @wraps(f)
    @login_required
    def d(*a,**kw):
        if current_user.role != 'admin':
            flash('Access denied.','error'); return redirect(url_for('pos.pos'))
        return f(*a,**kw)
    return d

@users_bp.route('/users')
@admin_required
def users():
    return render_template('users.html', users=User.query.order_by(User.username).all())

@users_bp.route('/api/users', methods=['POST'])
@admin_required
def api_add():
    d = request.get_json() or {}
    u = d.get('username','').strip()
    if not u: return jsonify({'error':'Username required'}), 400
    if User.query.filter_by(username=u).first(): return jsonify({'error':'Username exists'}), 400
    pw = d.get('password','')
    if not pw or len(pw)<6: return jsonify({'error':'Password min 6 chars'}), 400
    role = d.get('role','cashier')
    if role not in User.ROLES: return jsonify({'error':'Invalid role'}), 400
    import secrets, string
    colors = ['#F0883E','#3FB950','#58A6FF','#D29922','#BC8CFF','#FF6B6B']
    user = User(username=u, full_name=d.get('full_name',''), role=role,
                avatar_color=secrets.choice(colors))
    user.set_password(pw)
    user.security_question=d.get('q1',''); user.security_question2=d.get('q2',''); user.security_question3=d.get('q3','')
    user.set_security_answers(d.get('a1','x'), d.get('a2','x'), d.get('a3','x'))
    db.session.add(user); db.session.commit()
    audit('USER_ADD', f'{u} role={role}')
    return jsonify({'success':True,'id':user.id})

@users_bp.route('/api/users/<int:uid>', methods=['PUT'])
@admin_required
def api_edit(uid):
    u = db.session.get(User, uid)
    if not u: return jsonify({'error':'Not found'}), 404
    d = request.get_json() or {}
    u.full_name = d.get('full_name', u.full_name)
    role = d.get('role', u.role)
    if role not in User.ROLES: return jsonify({'error':'Invalid role'}), 400
    u.role = role
    if d.get('q1'): u.security_question = d['q1']
    if d.get('q2'): u.security_question2 = d['q2']
    if d.get('q3'): u.security_question3 = d['q3']
    if d.get('a1') and d.get('a2') and d.get('a3'):
        u.set_security_answers(d['a1'], d['a2'], d['a3'])
    db.session.commit(); audit('USER_EDIT', f'{u.username}')
    return jsonify({'success':True})

@users_bp.route('/api/users/<int:uid>/reset-password', methods=['POST'])
@admin_required
def api_reset(uid):
    u = db.session.get(User, uid)
    if not u: return jsonify({'error':'Not found'}), 404
    pw = (request.get_json() or {}).get('password','')
    if not pw or len(pw)<6: return jsonify({'error':'Password min 6 chars'}), 400
    u.set_password(pw); db.session.commit()
    audit('PASSWORD_RESET', f'Reset: {u.username}')
    return jsonify({'success':True})

@users_bp.route('/api/users/<int:uid>/toggle', methods=['POST'])
@admin_required
def api_toggle(uid):
    u = db.session.get(User, uid)
    if not u: return jsonify({'error':'Not found'}), 404
    if u.id == current_user.id: return jsonify({'error':'Cannot deactivate yourself'}), 400
    u.is_active = not u.is_active; db.session.commit()
    audit('USER_TOGGLE', f'{u.username} active={u.is_active}')
    return jsonify({'success':True,'is_active':u.is_active})

@users_bp.route('/api/users/<int:uid>', methods=['DELETE'])
@admin_required
def api_delete(uid):
    u = db.session.get(User, uid)
    if not u: return jsonify({'error':'Not found'}), 404
    if u.id == current_user.id: return jsonify({'error':'Cannot delete yourself'}), 400
    uname = u.username; db.session.delete(u); db.session.commit()
    audit('USER_DELETE', f'{uname}')
    return jsonify({'success':True})
