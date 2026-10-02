"""3. Cart & Order module – cart, wishlist, checkout, order history, tracking."""
import re

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from extensions import db
from models import CartItem, Order, OrderItem, Product, WishlistItem
from services import StockError, cancel_order, cart_summary, check_stock, confirm_order, new_payment
from utils.notify import order_status_mail

bp = Blueprint("cart", __name__)


def _back(default):
    ref = request.form.get("back") or request.referrer
    return redirect(ref or default)


def _require_login_for_post(product_id):
    flash("Log in to save items to your cart or wishlist.", "info")
    return redirect(url_for("auth.login",
                            next=url_for("products.product_detail", product_id=product_id)))


# ---------------------------------------------------------------- cart ------
@bp.route("/cart")
@login_required
def view_cart():
    items, subtotal, shipping, total = cart_summary(current_user.user_id)
    return render_template("orders/cart.html", items=items, subtotal=subtotal,
                           shipping=shipping, total=total)


@bp.route("/cart/add/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):
    if not current_user.is_authenticated:
        return _require_login_for_post(product_id)
    product = Product.query.filter_by(product_id=product_id, is_active=True).first_or_404()
    qty = max(1, request.form.get("quantity", 1, type=int))
    item = CartItem.query.filter_by(user_id=current_user.user_id, product_id=product_id).first()
    wanted = qty + (item.quantity if item else 0)
    if product.stock == 0:
        flash(f"{product.name} is out of stock.", "error")
        return _back(url_for("products.product_detail", product_id=product_id))
    if wanted > product.stock:
        wanted = product.stock
        flash(f"Only {product.stock} available, so your cart has the maximum.", "info")
    else:
        flash(f"Added {product.name} to your cart.", "success")
    if item:
        item.quantity = wanted
    else:
        db.session.add(CartItem(user_id=current_user.user_id, product_id=product_id, quantity=wanted))
    db.session.commit()
    if request.form.get("buy_now"):
        return redirect(url_for("cart.checkout"))
    return _back(url_for("cart.view_cart"))


@bp.route("/cart/update/<int:item_id>", methods=["POST"])
@login_required
def update_cart(item_id):
    item = CartItem.query.filter_by(cart_item_id=item_id, user_id=current_user.user_id).first_or_404()
    qty = request.form.get("quantity", type=int) or 0
    if qty <= 0:
        db.session.delete(item)
        flash(f"Removed {item.product.name}.", "info")
    else:
        item.quantity = min(qty, max(item.product.stock, 1))
        if qty > item.product.stock:
            flash(f"Only {item.product.stock} of {item.product.name} available.", "info")
    db.session.commit()
    return redirect(url_for("cart.view_cart"))


@bp.route("/cart/remove/<int:item_id>", methods=["POST"])
@login_required
def remove_from_cart(item_id):
    item = CartItem.query.filter_by(cart_item_id=item_id, user_id=current_user.user_id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    flash(f"Removed {item.product.name}.", "info")
    return redirect(url_for("cart.view_cart"))


# ------------------------------------------------------------ wishlist -----
@bp.route("/wishlist")
@login_required
def wishlist():
    items = (WishlistItem.query.filter_by(user_id=current_user.user_id)
             .order_by(WishlistItem.created_at.desc()).all())
    return render_template("orders/wishlist.html", items=items)


@bp.route("/wishlist/toggle/<int:product_id>", methods=["POST"])
def toggle_wishlist(product_id):
    if not current_user.is_authenticated:
        return _require_login_for_post(product_id)
    product = db.get_or_404(Product, product_id)
    item = WishlistItem.query.filter_by(user_id=current_user.user_id, product_id=product_id).first()
    if item:
        db.session.delete(item)
        flash(f"Removed {product.name} from your wishlist.", "info")
    else:
        db.session.add(WishlistItem(user_id=current_user.user_id, product_id=product_id))
        flash(f"Saved {product.name} to your wishlist.", "success")
    db.session.commit()
    return _back(url_for("cart.wishlist"))


@bp.route("/wishlist/move/<int:product_id>", methods=["POST"])
@login_required
def move_to_cart(product_id):
    item = WishlistItem.query.filter_by(user_id=current_user.user_id,
                                        product_id=product_id).first_or_404()
    product = item.product
    if not product.is_active or product.stock == 0:
        flash(f"{product.name} is out of stock right now.", "error")
        return redirect(url_for("cart.wishlist"))
    cart = CartItem.query.filter_by(user_id=current_user.user_id, product_id=product_id).first()
    if not cart:
        db.session.add(CartItem(user_id=current_user.user_id, product_id=product_id, quantity=1))
    db.session.delete(item)
    db.session.commit()
    flash(f"Moved {product.name} to your cart.", "success")
    return redirect(url_for("cart.wishlist"))


# ------------------------------------------------------------ checkout -----
@bp.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    items, subtotal, shipping, total = cart_summary(current_user.user_id)
    if not items:
        flash("Your cart is empty. Add something first.", "info")
        return redirect(url_for("products.shop"))

    last = (Order.query.filter_by(user_id=current_user.user_id)
            .order_by(Order.order_date.desc()).first())
    form = request.form if request.method == "POST" else {
        "ship_name": last.ship_name if last else current_user.name,
        "ship_phone": last.ship_phone if last else (current_user.phone or ""),
        "ship_address": last.ship_address if last else "",
        "ship_city": last.ship_city if last else "",
        "ship_pincode": last.ship_pincode if last else "",
        "payment_method": "online",
    }

    if request.method == "POST":
        f = {k: request.form.get(k, "").strip() for k in
             ("ship_name", "ship_phone", "ship_address", "ship_city", "ship_pincode", "payment_method")}
        errors = []
        if len(f["ship_name"]) < 2:
            errors.append("Enter the receiver's name.")
        if not re.fullmatch(r"[6-9]\d{9}", f["ship_phone"]):
            errors.append("Enter a 10-digit mobile number.")
        if len(f["ship_address"]) < 8:
            errors.append("Enter the full delivery address.")
        if len(f["ship_city"]) < 2:
            errors.append("Enter the city.")
        if not re.fullmatch(r"\d{6}", f["ship_pincode"]):
            errors.append("PIN code must be 6 digits.")
        if f["payment_method"] not in ("online", "cod"):
            errors.append("Choose a payment method.")
        try:
            check_stock(items)
        except StockError as e:
            errors.append(f"{e} Update your cart and try again.")
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("orders/checkout.html", items=items, subtotal=subtotal,
                                   shipping=shipping, total=total, form=request.form)

        is_cod = f["payment_method"] == "cod"
        order = Order(user_id=current_user.user_id, subtotal=subtotal, shipping_fee=shipping,
                      total_amount=total, payment_method="COD" if is_cod else "Online",
                      status="Pending Payment",
                      **{k: v for k, v in f.items() if k.startswith("ship_")})
        for i in items:
            order.items.append(OrderItem(product_id=i.product_id, quantity=i.quantity,
                                         unit_price=i.product.price))
        db.session.add(order)
        db.session.flush()  # assigns order_id and loads item.product

        if is_cod:
            confirm_order(order)
            new_payment(order, "COD", "Pending")
            db.session.commit()
            order_status_mail(order)
            flash(f"Order {order.number} placed. Pay in cash on delivery.", "success")
            return redirect(url_for("cart.order_detail", order_id=order.order_id))

        new_payment(order, "Online", "Created")
        db.session.commit()
        return redirect(url_for("payment.pay", order_id=order.order_id))

    return render_template("orders/checkout.html", items=items, subtotal=subtotal,
                           shipping=shipping, total=total, form=form)


# -------------------------------------------------------------- orders -----
def _my_order(order_id):
    order = db.session.get(Order, order_id)
    if not order or (order.user_id != current_user.user_id and not current_user.is_admin):
        abort(404)
    return order


@bp.route("/orders")
@login_required
def orders():
    status = request.args.get("status")
    query = Order.query.filter_by(user_id=current_user.user_id)
    if status in Order.STATUSES:
        query = query.filter_by(status=status)
    return render_template("orders/orders.html",
                           orders=query.order_by(Order.order_date.desc()).all(), status=status)


@bp.route("/orders/<int:order_id>")
@login_required
def order_detail(order_id):
    return render_template("orders/order_detail.html", order=_my_order(order_id))


@bp.route("/orders/<int:order_id>/cancel", methods=["POST"])
@login_required
def cancel(order_id):
    order = _my_order(order_id)
    if not order.can_cancel:
        flash("This order has already shipped and can't be cancelled.", "error")
    else:
        refund = order.payment and order.payment.status == "Success"
        cancel_order(order)
        db.session.commit()
        order_status_mail(order)
        flash(f"Order {order.number} cancelled." +
              (" Your refund has been initiated." if refund else ""), "success")
    return redirect(url_for("cart.order_detail", order_id=order_id))
