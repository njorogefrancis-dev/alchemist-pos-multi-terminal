from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime, timedelta, timezone
from models import db
from models.user import User
from models.helpers import audit

auth_bp = Blueprint('auth', __name__)

def no_users():
    return User.query.count() == 0

@auth_bp.route('/setup', methods=['GET', 'POST'])
def setup():
    if not no_users():
        return redirect(url_for('auth.login'))
    if request.method == 'POST':
        u = request.form.get('username','').strip()
        p = request.form.get('password','')
        c = request.form.get('confirm_password','')
        fn = request.form.get('full_name','').strip()
        if not u or not p:
            flash('Username and password required.', 'error'); return render_template('setup.html')
        if p != c:
            flash('Passwords do not match.', 'error'); return render_template('setup.html')
        if len(p) < 6:
            flash('Password must be at least 6 characters.', 'error'); return render_template('setup.html')
        user = User(username=u, role='admin', full_name=fn)
        user.set_password(p)
        user.security_question  = request.form.get('q1','')
        user.security_question2 = request.form.get('q2','')
        user.security_question3 = request.form.get('q3','')
        user.set_security_answers(request.form.get('a1','x'), request.form.get('a2','x'), request.form.get('a3','x'))
        db.session.add(user); db.session.commit()
        audit('SETUP', f'Admin created: {u}', user=user)
        flash('Setup complete! Welcome to AlchemyPOS.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('setup.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if no_users(): return redirect(url_for('auth.setup'))
    if current_user.is_authenticated: return redirect(url_for('pos.pos'))
    if request.method == 'POST':
        u = request.form.get('username','').strip()
        p = request.form.get('password','')
        user = User.query.filter_by(username=u).first()
        if not user or not user.is_active:
            flash('Invalid credentials.', 'error'); return render_template('login.html')
        if user.is_locked():
            flash(f'Account locked. Try again in {user.lock_remaining_minutes()} minute(s).', 'error')
            return render_template('login.html')
        if not user.check_password(p):
            user.failed_attempts += 1
            if user.failed_attempts >= 5:
                user.locked_until = datetime.utcnow() + timedelta(minutes=15)
                user.failed_attempts = 0
                db.session.commit()
                audit('LOGIN_LOCKED', f'Locked: {u}')
                flash('Account locked for 15 minutes after 5 failed attempts.', 'error')
            else:
                db.session.commit()
                flash(f'Invalid password. {5 - user.failed_attempts} attempt(s) remaining.', 'error')
            return render_template('login.html')
        user.failed_attempts = 0
        user.locked_until = None
        user.last_login = datetime.utcnow()
        db.session.commit()
        login_user(user, remember=False)
        session.permanent = True
        audit('LOGIN', f'Login: {u}', user=user)
        return redirect(request.args.get('next') or url_for('pos.pos'))
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    audit('LOGOUT', f'Logout: {current_user.username}')
    logout_user()
    return redirect(url_for('auth.login'))

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    step = '1'
    username = ''
    q1=q2=q3=''
    if request.method == 'POST':
        step = request.form.get('step','1')
        username = request.form.get('username','').strip()
        user = User.query.filter_by(username=username, is_active=True).first()
        if step == '1':
            if not user: flash('Username not found.','error'); return render_template('forgot_password.html', step='1')
            return render_template('forgot_password.html', step='2', username=username,
                q1=user.security_question, q2=user.security_question2, q3=user.security_question3)
        elif step == '2':
            if not user: return redirect(url_for('auth.forgot_password'))
            a1,a2,a3 = request.form.get('a1',''), request.form.get('a2',''), request.form.get('a3','')
            if user.check_security_answers(a1,a2,a3):
                session['pw_reset_uid'] = user.id
                return render_template('forgot_password.html', step='3', username=username)
            flash('One or more answers incorrect.','error')
            return render_template('forgot_password.html', step='2', username=username,
                q1=user.security_question, q2=user.security_question2, q3=user.security_question3)
        elif step == '3':
            uid = session.get('pw_reset_uid')
            if not uid: flash('Session expired.','error'); return redirect(url_for('auth.forgot_password'))
            new_pw = request.form.get('new_password','')
            if len(new_pw) < 6: flash('Password too short.','error'); return render_template('forgot_password.html', step='3', username=username)
            real = db.session.get(User, uid)
            real.set_password(new_pw); db.session.commit()
            session.pop('pw_reset_uid', None)
            audit('PASSWORD_RESET', f'Reset via security questions: {real.username}')
            flash('Password reset successfully.', 'success')
            return redirect(url_for('auth.login'))
    return render_template('forgot_password.html', step='1')
