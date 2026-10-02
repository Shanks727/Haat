"""Database models. Table and column names follow the Data Schema Design
(Chapter 4.3) of the project report. Extra tables: cart_items and wishlist."""
from datetime import datetime
from decimal import Decimal

from flask_login import UserMixin
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db


def now():
    return datetime.now()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    user_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(15))
    role = db.Column(db.String(15), nullable=False, default="customer")   # customer | admin
    status = db.Column(db.String(20), nullable=False, default="active")   # active | blocked
    created_at = db.Column(db.DateTime, default=now)

    orders = db.relationship("Order", backref="user", lazy="dynamic")

    def get_id(self):
        return str(self.user_id)

    def set_password(self, raw):
        self.password = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password, raw)

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def is_active(self):
        return self.status == "active"


class Category(db.Model):
    __tablename__ = "categories"

    category_id = db.Column(db.Integer, primary_key=True)
    category_name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=now)

    products = db.relationship("Product", backref="category", lazy="dynamic")


class Product(db.Model):
    __tablename__ = "products"

    product_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.category_id"), nullable=False)
    image = db.Column(db.String(255))                      # file name in static/uploads
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=now)

    reviews = db.relationship("Review", backref="product", lazy="dynamic",
                              cascade="all, delete-orphan")

    @property
    def rating_avg(self):
        value = db.session.query(func.avg(Review.rating)).filter(
            Review.product_id == self.product_id).scalar()
        return round(float(value), 1) if value else 0

    @property
    def rating_count(self):
        return self.reviews.count()

    @property
    def in_stock(self):
        return self.stock > 0


class Order(db.Model):
    __tablename__ = "orders"
    STATUSES = ["Pending Payment", "Placed", "Shipped", "Delivered", "Cancelled"]

    order_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    order_date = db.Column(db.DateTime, default=now, index=True)
    status = db.Column(db.String(20), nullable=False, default="Pending Payment")
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    shipping_fee = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    payment_method = db.Column(db.String(30), nullable=False)   # Online | COD

    ship_name = db.Column(db.String(100), nullable=False)
    ship_phone = db.Column(db.String(15), nullable=False)
    ship_address = db.Column(db.String(255), nullable=False)
    ship_city = db.Column(db.String(60), nullable=False)
    ship_pincode = db.Column(db.String(10), nullable=False)

    shipped_at = db.Column(db.DateTime)
    delivered_at = db.Column(db.DateTime)
    cancelled_at = db.Column(db.DateTime)

    items = db.relationship("OrderItem", backref="order", cascade="all, delete-orphan")
    payments = db.relationship("Payment", backref="order", cascade="all, delete-orphan",
                               order_by="Payment.payment_id")

    @property
    def number(self):
        return f"HT{self.order_id:06d}"

    @property
    def payment(self):
        return self.payments[-1] if self.payments else None

    @property
    def item_count(self):
        return sum(i.quantity for i in self.items)

    @property
    def can_cancel(self):
        return self.status in ("Pending Payment", "Placed")

    @property
    def is_confirmed(self):
        return self.status in ("Placed", "Shipped", "Delivered")


class OrderItem(db.Model):
    __tablename__ = "order_items"

    item_id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.order_id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.product_id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)

    product = db.relationship("Product")

    @property
    def line_total(self):
        return self.unit_price * self.quantity


class Payment(db.Model):
    __tablename__ = "payments"

    payment_id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.order_id"), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    method = db.Column(db.String(30), nullable=False)          # Razorpay | Demo | COD
    status = db.Column(db.String(20), nullable=False, default="Created")
    # Created | Success | Failed | Pending | Cancelled | Refund Initiated
    gateway_order_id = db.Column(db.String(64))
    gateway_payment_id = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, default=now)
    paid_at = db.Column(db.DateTime)


class Review(db.Model):
    __tablename__ = "reviews"
    __table_args__ = (db.UniqueConstraint("user_id", "product_id", name="uq_review_user_product"),)

    review_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.product_id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=now)

    user = db.relationship("User")


class CartItem(db.Model):
    __tablename__ = "cart_items"
    __table_args__ = (db.UniqueConstraint("user_id", "product_id", name="uq_cart_user_product"),)

    cart_item_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.product_id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    added_at = db.Column(db.DateTime, default=now)

    product = db.relationship("Product")

    @property
    def line_total(self):
        return self.product.price * self.quantity


class WishlistItem(db.Model):
    __tablename__ = "wishlist"
    __table_args__ = (db.UniqueConstraint("user_id", "product_id", name="uq_wish_user_product"),)

    wishlist_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.product_id"), nullable=False)
    created_at = db.Column(db.DateTime, default=now)

    product = db.relationship("Product")


ZERO = Decimal("0.00")
