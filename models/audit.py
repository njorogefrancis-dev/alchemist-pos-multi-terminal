from datetime import datetime, timezone
from models import db


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    username   = db.Column(db.String(80), default='')
    action     = db.Column(db.String(80), nullable=False, index=True)
    details    = db.Column(db.Text, default='')
    ip_address = db.Column(db.String(45), default='')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class Setting(db.Model):
    __tablename__ = 'settings'
    key   = db.Column(db.String(80), primary_key=True)
    value = db.Column(db.Text, default='')


class Backup(db.Model):
    __tablename__ = 'backups'
    id         = db.Column(db.Integer, primary_key=True)
    filename   = db.Column(db.String(200), nullable=False)
    path       = db.Column(db.String(500), nullable=False)
    size_bytes = db.Column(db.Integer, default=0)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    notes      = db.Column(db.String(300), default='')
    creator    = db.relationship('User', foreign_keys=[created_by])
