from datetime import datetime, timezone
from models import db


class Category(db.Model):
    __tablename__ = 'categories'
    id   = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(200), default='')
    icon = db.Column(db.String(10), default='📦')
    color = db.Column(db.String(10), default='#F0883E')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class Product(db.Model):
    __tablename__ = 'products'
    id       = db.Column(db.Integer, primary_key=True)
    barcode  = db.Column(db.String(80), default='', index=True)
    name     = db.Column(db.String(150), nullable=False, index=True)
    category = db.Column(db.String(80), default='General')
    price    = db.Column(db.Numeric(12, 2), default=0)
    cost     = db.Column(db.Numeric(12, 2), default=0)
    unit     = db.Column(db.String(30), default='pcs')
    description = db.Column(db.String(300), default='')
    image_url   = db.Column(db.String(300), default='')
    is_active   = db.Column(db.Boolean, default=True)
    is_featured = db.Column(db.Boolean, default=False)
    created_at  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                            onupdate=lambda: datetime.now(timezone.utc))

    inventory  = db.relationship('Inventory', backref='product', uselist=False, lazy='joined')
    sale_items = db.relationship('SaleItem', backref='product', lazy='dynamic')

    def stock(self):
        return float(self.inventory.quantity) if self.inventory else 0

    def is_out_of_stock(self):
        return self.stock() <= 0

    def is_low_stock(self):
        if not self.inventory: return False
        return 0 < self.stock() <= float(self.inventory.low_stock_threshold)

    def price_float(self):
        return float(self.price)

    def cost_float(self):
        return float(self.cost)

    def margin_pct(self):
        if self.cost and float(self.cost) > 0:
            return round((float(self.price) - float(self.cost)) / float(self.cost) * 100, 1)
        return 0


class Inventory(db.Model):
    __tablename__ = 'inventory'
    id          = db.Column(db.Integer, primary_key=True)
    product_id  = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, unique=True)
    quantity    = db.Column(db.Numeric(12, 3), default=0)
    low_stock_threshold = db.Column(db.Numeric(12, 3), default=5)
    last_updated = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
