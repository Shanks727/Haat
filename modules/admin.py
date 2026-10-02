"""5. Admin module – dashboard, products, categories, orders, users,
review moderation, and sales analytics/reports."""
import csv
import io
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal

from flask import (Blueprint, Response, current_app, flash, redirect, render_template,
                   request, url_for)
from flask_login import current_user
from sqlalchemy import func, or_

from extensions import db
from models import Category, Order, OrderItem, Payment, Product, Review, User
from services import advance_order
from utils.helpers import admin_required, save_image
from utils.notify import order_status_mail

bp = Blueprint("admin", __name__, url_prefix="/admin")
CONFIRMED = ["Placed", "Shipped", "Delivered"]


@bp.before_request
@admin_required
def guard():
    """Every /admin route requires an admin account."""
    return None


# ----------------------------------------------------------- dashboard -----
@bp.route("/")
def dashboard():
    confirmed = Order.query.filter(Order.status.in_(CONFIRMED))
    revenue = db.session.query(func.coalesce(func.sum(Order.total_amount), 0)) \
        .filter(Order.status.in_(CONFIRMED)).scalar()
    kpis = {
        "revenue": revenue,
        "orders": confirmed.count(),
        "to_ship": Order.query.filter_by(status="Placed").count(),
        "customers": User.query.filter_by(role="customer").count(),
        "low_stock": Product.query.filter(Product.is_active.is_(True),
                                          Product.stock <= current_app.config["LOW_STOCK_LIMIT"]).count(),
    }

    # Revenue per day, last 14 days (aggregated in Python: works on MySQL and SQLite)
    start = date.today() - timedelta(days=13)
    per_day = defaultdict(Decimal)
    for o in confirmed.filter(Order.order_date >= datetime.combine(start, datetime.min.time())):
        per_day[o.order_date.date()] += o.total_amount
    days = [start + timedelta(days=i) for i in range(14)]
    sales_chart = {"labels": [d.strftime("%d %b") for d in days],
                   "values": [float(per_day[d]) for d in days]}

    status_rows = dict(db.session.query(Order.status, func.count(Order.order_id))
                       .group_by(Order.status).all())
    status_chart = {"labels": Order.STATUSES, "values": [status_rows.get(s, 0) for s in Order.STATUSES]}

    top_products = (db.session.query(Product.name, func.sum(OrderItem.quantity).label("qty"),
                                     func.sum(OrderItem.quantity * OrderItem.unit_price).label("amt"))
                    .join(OrderItem, OrderItem.product_id == Product.product_id)
                    .join(Order, Order.order_id == OrderItem.order_id)
                    .filter(Order.status.in_(CONFIRMED))
                    .group_by(Product.product_id, Product.name)
                    .order_by(func.sum(OrderItem.quantity).desc()).limit(5).all())
    recent = Order.query.order_by(Order.order_date.desc()).limit(6).all()
    low = (Product.query.filter(Product.is_active.is_(True),
                                Product.stock <= current_app.config["LOW_STOCK_LIMIT"])
           .order_by(Product.stock).limit(6).all())
    return render_template("admin/dashboard.html", kpis=kpis, sales_chart=sales_chart,
                           status_chart=status_chart, top_products=top_products,
                           recent=recent, low=low)


# ------------------------------------------------------------ products -----
@bp.route("/products")
def products():
    q = request.args.get("q", "").strip()
    cat = request.args.get("category", type=int)
    query = Product.query
    if q:
        query = query.filter(Product.name.ilike(f"%{q}%"))
    if cat:
        query = query.filter_by(category_id=cat)
    pagination = query.order_by(Product.is_active.desc(), Product.name).paginate(
        page=request.args.get("page", 1, type=int), per_page=15, error_out=False)
    return render_template("admin/products.html", pagination=pagination, q=q, cat=cat,
                           categories=Category.query.order_by(Category.category_name).all())


def _product_form(product=None):
    categories = Category.query.order_by(Category.category_name).all()
    if not categories:
        flash("Create a category before adding products.", "info")
        return redirect(url_for("admin.categories"))
    if request.method == "POST":
        f = request.form
        errors = []
        name = f.get("name", "").strip()
        try:
            price = Decimal(f.get("price", "")).quantize(Decimal("0.01"))
            if price <= 0:
                raise ValueError
        except Exception:
            price = None
            errors.append("Price must be a number above 0.")
        stock = f.get("stock", type=int)
        if len(name) < 2:
            errors.append("Product name is required.")
        if stock is None or stock < 0:
            errors.append("Stock must be 0 or more.")
        cat_id = f.get("category_id", type=int)
        if not db.session.get(Category, cat_id or 0):
            errors.append("Choose a category.")
        image = None
        try:
            image = save_image(request.files.get("image"))
        except ValueError as e:
            errors.append(str(e))
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("admin/product_form.html", product=product, form=f,
                                   categories=categories)
        is_new = product is None
        if is_new:
            product = Product()
            db.session.add(product)
        product.name, product.price, product.stock = name, price, stock
        product.category_id = cat_id
        product.description = f.get("description", "").strip()
        product.is_active = bool(f.get("is_active"))
        if image:
            product.image = image
        if f.get("remove_image"):
            product.image = None
        db.session.commit()
        flash(f"{'Added' if is_new else 'Saved'} {product.name}.", "success")
        return redirect(url_for("admin.products"))
    form = {} if product is None else {
        "name": product.name, "price": product.price, "stock": product.stock,
        "category_id": product.category_id, "description": product.description or "",
        "is_active": product.is_active}
    if product is None:
        form["is_active"] = True
    return render_template("admin/product_form.html", product=product, form=form,
                           categories=categories)


@bp.route("/products/new", methods=["GET", "POST"])
def product_new():
    return _product_form()


@bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
def product_edit(product_id):
    return _product_form(db.get_or_404(Product, product_id))


@bp.route("/products/<int:product_id>/delete", methods=["POST"])
def product_delete(product_id):
    product = db.get_or_404(Product, product_id)
    if OrderItem.query.filter_by(product_id=product_id).first():
        product.is_active = False
        flash(f"{product.name} has past orders, so it was hidden instead of deleted.", "info")
    else:
        db.session.delete(product)
        flash(f"Deleted {product.name}.", "success")
    db.session.commit()
    return redirect(url_for("admin.products"))


# ---------------------------------------------------------- categories -----
@bp.route("/categories", methods=["GET", "POST"])
def categories():
    edit = None
    if request.args.get("edit", type=int):
        edit = db.get_or_404(Category, request.args.get("edit", type=int))
    if request.method == "POST":
        cid = request.form.get("category_id", type=int)
        name = request.form.get("category_name", "").strip()
        desc = request.form.get("description", "").strip()
        clash = Category.query.filter(func.lower(Category.category_name) == name.lower(),
                                      Category.category_id != (cid or 0)).first()
        if len(name) < 2:
            flash("Category name is required.", "error")
        elif clash:
            flash(f"A category called {name} already exists.", "error")
        else:
            cat = db.get_or_404(Category, cid) if cid else Category()
            cat.category_name, cat.description = name, desc
            db.session.add(cat)
            db.session.commit()
            flash(f"Saved category {name}.", "success")
            return redirect(url_for("admin.categories"))
    rows = (db.session.query(Category, func.count(Product.product_id))
            .outerjoin(Product, Product.category_id == Category.category_id)
            .group_by(Category.category_id).order_by(Category.category_name).all())
    return render_template("admin/categories.html", rows=rows, edit=edit)


@bp.route("/categories/<int:category_id>/delete", methods=["POST"])
def category_delete(category_id):
    cat = db.get_or_404(Category, category_id)
    if cat.products.count():
        flash(f"Move or delete the products in {cat.category_name} first.", "error")
    else:
        db.session.delete(cat)
        db.session.commit()
        flash(f"Deleted category {cat.category_name}.", "success")
    return redirect(url_for("admin.categories"))


# -------------------------------------------------------------- orders -----
@bp.route("/orders")
def orders():
    status = request.args.get("status")
    q = request.args.get("q", "").strip()
    query = Order.query.join(User, User.user_id == Order.user_id)
    if status in Order.STATUSES:
        query = query.filter(Order.status == status)
    if q:
        digits = "".join(ch for ch in q if ch.isdigit())
        conds = [User.name.ilike(f"%{q}%"), User.email.ilike(f"%{q}%")]
        if digits:
            conds.append(Order.order_id == int(digits))
        query = query.filter(or_(*conds))
    pagination = query.order_by(Order.order_date.desc()).paginate(
        page=request.args.get("page", 1, type=int), per_page=20, error_out=False)
    counts = dict(db.session.query(Order.status, func.count(Order.order_id)).group_by(Order.status).all())
    return render_template("admin/orders.html", pagination=pagination, status=status, q=q,
                           counts=counts)


@bp.route("/orders/<int:order_id>", methods=["GET", "POST"])
def order_detail(order_id):
    order = db.get_or_404(Order, order_id)
    if request.method == "POST":
        error = advance_order(order, request.form.get("status", ""))
        if error:
            flash(error, "error")
        else:
            db.session.commit()
            order_status_mail(order)
            flash(f"Order {order.number} marked {order.status}.", "success")
        return redirect(url_for("admin.order_detail", order_id=order_id))
    return render_template("admin/order_detail.html", order=order)


# --------------------------------------------------------------- users -----
@bp.route("/users")
def users():
    q = request.args.get("q", "").strip()
    query = User.query
    if q:
        query = query.filter(or_(User.name.ilike(f"%{q}%"), User.email.ilike(f"%{q}%")))
    spend = dict(db.session.query(Order.user_id, func.sum(Order.total_amount))
                 .filter(Order.status.in_(CONFIRMED)).group_by(Order.user_id).all())
    orders = dict(db.session.query(Order.user_id, func.count(Order.order_id))
                  .group_by(Order.user_id).all())
    return render_template("admin/users.html", users=query.order_by(User.created_at.desc()).all(),
                           q=q, spend=spend, orders=orders)


@bp.route("/users/<int:user_id>/toggle", methods=["POST"])
def user_toggle(user_id):
    user = db.get_or_404(User, user_id)
    if user.is_admin or user.user_id == current_user.user_id:
        flash("Admin accounts can't be blocked here.", "error")
    else:
        user.status = "active" if user.status == "blocked" else "blocked"
        db.session.commit()
        flash(f"{user.name} is now {user.status}.", "success")
    return redirect(request.referrer or url_for("admin.users"))


# ------------------------------------------------------------- reviews -----
@bp.route("/reviews")
def reviews():
    rating = request.args.get("rating", type=int)
    query = Review.query
    if rating:
        query = query.filter_by(rating=rating)
    return render_template("admin/reviews.html", rating=rating,
                           reviews=query.order_by(Review.created_at.desc()).limit(200).all())


# ------------------------------------------------------------- reports -----
@bp.route("/reports")
def reports():
    today = date.today()
    try:
        d_from = datetime.strptime(request.args.get("from", ""), "%Y-%m-%d").date()
    except ValueError:
        d_from = today - timedelta(days=29)
    try:
        d_to = datetime.strptime(request.args.get("to", ""), "%Y-%m-%d").date()
    except ValueError:
        d_to = today
    if d_from > d_to:
        d_from, d_to = d_to, d_from
    start = datetime.combine(d_from, datetime.min.time())
    end = datetime.combine(d_to + timedelta(days=1), datetime.min.time())

    orders = (Order.query.filter(Order.status.in_(CONFIRMED), Order.order_date >= start,
                                 Order.order_date < end)
              .order_by(Order.order_date).all())

    if request.args.get("format") == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["Order", "Date", "Customer", "Email", "Items", "Subtotal", "Shipping",
                    "Total", "Payment", "Status"])
        for o in orders:
            w.writerow([o.number, o.order_date.strftime("%Y-%m-%d %H:%M"), o.user.name, o.user.email,
                        o.item_count, o.subtotal, o.shipping_fee, o.total_amount,
                        o.payment_method, o.status])
        return Response(buf.getvalue(), mimetype="text/csv", headers={
            "Content-Disposition": f"attachment; filename=sales_{d_from}_{d_to}.csv"})

    total = sum((o.total_amount for o in orders), Decimal("0"))
    items_sold = sum(o.item_count for o in orders)
    by_cat, by_product, by_method = defaultdict(Decimal), defaultdict(lambda: [0, Decimal("0")]), defaultdict(int)
    for o in orders:
        by_method[o.payment_method] += 1
        for it in o.items:
            by_cat[it.product.category.category_name] += it.line_total
            by_product[it.product.name][0] += it.quantity
            by_product[it.product.name][1] += it.line_total
    summary = {"revenue": total, "orders": len(orders), "items": items_sold,
               "aov": (total / len(orders)) if orders else Decimal("0")}
    cats = sorted(by_cat.items(), key=lambda kv: kv[1], reverse=True)
    prods = sorted(by_product.items(), key=lambda kv: kv[1][1], reverse=True)[:10]
    failed = Payment.query.filter(Payment.status == "Failed", Payment.created_at >= start,
                                  Payment.created_at < end).count()
    return render_template("admin/reports.html", d_from=d_from, d_to=d_to, summary=summary,
                           cats=cats, prods=prods, by_method=dict(by_method), failed=failed,
                           orders=orders)
