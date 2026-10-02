"""2. Product module – home, catalogue browsing, search, filters, detail."""
from flask import Blueprint, current_app, render_template, request
from flask_login import current_user
from sqlalchemy import func, or_

from extensions import db
from models import Category, Order, OrderItem, Product, Review

bp = Blueprint("products", __name__)


def _rating_subquery():
    return (db.session.query(Review.product_id.label("pid"),
                             func.avg(Review.rating).label("avg"),
                             func.count(Review.review_id).label("cnt"))
            .group_by(Review.product_id).subquery())


@bp.route("/")
def home():
    active = Product.query.filter(Product.is_active.is_(True))
    newest = active.order_by(Product.created_at.desc()).limit(8).all()
    sq = _rating_subquery()
    top_rated = (active.join(sq, Product.product_id == sq.c.pid)
                 .order_by(sq.c.avg.desc(), sq.c.cnt.desc()).limit(4).all())
    counts = dict(db.session.query(Product.category_id, func.count(Product.product_id))
                  .filter(Product.is_active.is_(True)).group_by(Product.category_id).all())
    return render_template("shop/home.html", newest=newest, top_rated=top_rated, counts=counts)


@bp.route("/shop")
def shop():
    args = request.args
    q = args.get("q", "").strip()
    category_id = args.get("category", type=int)
    min_price = args.get("min", type=float)
    max_price = args.get("max", type=float)
    sort = args.get("sort", "newest")
    in_stock = args.get("in_stock") == "1"

    query = Product.query.filter(Product.is_active.is_(True))
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Product.name.ilike(like), Product.description.ilike(like)))
    if category_id:
        query = query.filter(Product.category_id == category_id)
    if min_price is not None:
        query = query.filter(Product.price >= min_price)
    if max_price is not None:
        query = query.filter(Product.price <= max_price)
    if in_stock:
        query = query.filter(Product.stock > 0)

    if sort == "price_asc":
        query = query.order_by(Product.price.asc())
    elif sort == "price_desc":
        query = query.order_by(Product.price.desc())
    elif sort == "rating":
        sq = _rating_subquery()
        query = (query.outerjoin(sq, Product.product_id == sq.c.pid)
                 .order_by(func.coalesce(sq.c.avg, 0).desc(), Product.name))
    else:
        sort = "newest"
        query = query.order_by(Product.created_at.desc(), Product.product_id.desc())

    pagination = query.paginate(page=args.get("page", 1, type=int),
                                per_page=current_app.config["PRODUCTS_PER_PAGE"],
                                error_out=False)
    category = db.session.get(Category, category_id) if category_id else None
    return render_template("shop/shop.html", pagination=pagination, q=q, category=category,
                           sort=sort, min_price=min_price, max_price=max_price, in_stock=in_stock)


@bp.route("/product/<int:product_id>")
def product_detail(product_id):
    product = Product.query.filter_by(product_id=product_id, is_active=True).first_or_404()
    reviews = product.reviews.order_by(Review.created_at.desc()).all()
    buyers = {uid for (uid,) in db.session.query(Order.user_id)
              .join(OrderItem, OrderItem.order_id == Order.order_id)
              .filter(OrderItem.product_id == product_id,
                      Order.status.in_(["Placed", "Shipped", "Delivered"])).distinct()}
    my_review = None
    if current_user.is_authenticated:
        my_review = next((r for r in reviews if r.user_id == current_user.user_id), None)
    breakdown = {s: 0 for s in range(5, 0, -1)}
    for r in reviews:
        breakdown[r.rating] += 1
    related = (Product.query.filter(Product.category_id == product.category_id,
                                    Product.product_id != product.product_id,
                                    Product.is_active.is_(True))
               .order_by(Product.created_at.desc()).limit(4).all())
    return render_template("shop/product.html", product=product, reviews=reviews,
                           buyers=buyers, my_review=my_review, breakdown=breakdown,
                           related=related)
