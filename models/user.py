from datetime import datetime, timezone, timedelta
from flask_login import UserMixin
from models import db, login_manager
import hashlib, os, hmac


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(30), nullable=False, default='cashier')
    full_name = db.Column(db.String(120), default='')
    email = db.Column(db.String(120), default='')
    avatar_color = db.Column(db.String(10), default='#F0883E')
    is_active = db.Column(db.Boolean, default=True)
    failed_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_login = db.Column(db.DateTime, nullable=True)
    security_question  = db.Column(db.String(200), default='')
    security_answer_hash  = db.Column(db.String(256), default='')
    security_question2 = db.Column(db.String(200), default='')
    security_answer2_hash = db.Column(db.String(256), default='')
    security_question3 = db.Column(db.String(200), default='')
    security_answer3_hash = db.Column(db.String(256), default='')

    sales = db.relationship('Sale', backref='cashier', lazy='dynamic', foreign_keys='Sale.cashier_id')
    audit_logs = db.relationship('AuditLog', backref='user', lazy='dynamic')

    ROLES = ['cashier', 'inventory_manager', 'admin']
    ROLE_LABELS = {'cashier': 'Cashier', 'inventory_manager': 'Inv. Manager', 'admin': 'Administrator'}

    def set_password(self, password):
        salt = os.urandom(16).hex()
        dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 310000)
        self.password_hash = f'pbkdf2:sha256:{salt}:{dk.hex()}'

    def check_password(self, password):
        try:
            _, alg, salt, hx = self.password_hash.split(':')
            dk = hashlib.pbkdf2_hmac(alg, password.encode(), salt.encode(), 310000)
            return hmac.compare_digest(dk.hex(), hx)
        except Exception:
            return False

    def _hash_answer(self, answer):
        salt = os.urandom(16).hex()
        dk = hashlib.pbkdf2_hmac('sha256', answer.lower().strip().encode(), salt.encode(), 100000)
        return f'pbkdf2:sha256:{salt}:{dk.hex()}'

    def _check_answer(self, stored, answer):
        if not stored: return False
        try:
            _, alg, salt, hx = stored.split(':')
            dk = hashlib.pbkdf2_hmac(alg, answer.lower().strip().encode(), salt.encode(), 100000)
            return hmac.compare_digest(dk.hex(), hx)
        except Exception:
            return False

    def set_security_answers(self, a1, a2, a3):
        self.security_answer_hash  = self._hash_answer(a1)
        self.security_answer2_hash = self._hash_answer(a2)
        self.security_answer3_hash = self._hash_answer(a3)

    def check_security_answers(self, a1, a2, a3):
        return (self._check_answer(self.security_answer_hash,  a1) and
                self._check_answer(self.security_answer2_hash, a2) and
                self._check_answer(self.security_answer3_hash, a3))

    def is_locked(self):
        if self.locked_until:
            lu = self.locked_until
            if lu.tzinfo is None:
                lu = lu.replace(tzinfo=timezone.utc)
            return lu > datetime.now(timezone.utc)
        return False

    def lock_remaining_minutes(self):
        if self.locked_until:
            lu = self.locked_until
            if lu.tzinfo is None: lu = lu.replace(tzinfo=timezone.utc)
            delta = lu - datetime.now(timezone.utc)
            if delta.total_seconds() > 0:
                return int(delta.total_seconds() // 60) + 1
        return 0

    def is_admin(self): return self.role == 'admin'
    def is_inventory_manager(self): return self.role in ('admin', 'inventory_manager')
    def role_label(self): return self.ROLE_LABELS.get(self.role, self.role)
    def initials(self):
        parts = (self.full_name or self.username).split()
        return ''.join(p[0] for p in parts[:2]).upper()


@login_manager.user_loader
def load_user(uid):
    return db.session.get(User, int(uid))
