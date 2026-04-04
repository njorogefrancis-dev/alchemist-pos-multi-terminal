from datetime import datetime, timezone
from models import db


class Sale(db.Model):
    __tablename__ = 'sales'
    id             = db.Column(db.Integer, primary_key=True)
    receipt_number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    cashier_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subtotal       = db.Column(db.Numeric(12, 2), default=0)
    discount       = db.Column(db.Numeric(12, 2), default=0)
    tax            = db.Column(db.Numeric(12, 2), default=0)
    total          = db.Column(db.Numeric(12, 2), default=0)
    payment_method = db.Column(db.String(30), default='cash')
    amount_tendered = db.Column(db.Numeric(12, 2), default=0)
    change_given   = db.Column(db.Numeric(12, 2), default=0)
    status         = db.Column(db.String(20), default='completed', index=True)
    notes          = db.Column(db.String(300), default='')
    created_at     = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    items = db.relationship('SaleItem', backref='sale', lazy='joined', cascade='all, delete-orphan')


class SaleItem(db.Model):
    __tablename__ = 'sale_items'
    id           = db.Column(db.Integer, primary_key=True)
    sale_id      = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False, index=True)
    product_id   = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    product_name = db.Column(db.String(150), nullable=False)
    quantity     = db.Column(db.Numeric(12, 3), default=1)
    unit_price   = db.Column(db.Numeric(12, 2), default=0)
    subtotal     = db.Column(db.Numeric(12, 2), default=0)


class PaymentMethod(db.Model):
    __tablename__ = 'payment_methods'
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(30), unique=True, nullable=False)
    label       = db.Column(db.String(60), nullable=False)
    icon        = db.Column(db.String(10), default='💳')
    description = db.Column(db.String(200), default='')
    is_active   = db.Column(db.Boolean, default=True)
    sort_order  = db.Column(db.Integer, default=0)
