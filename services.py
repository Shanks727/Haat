"""Order business rules shared by the cart, payment and admin modules."""
from decimal import Decimal

from flask import current_app

from extensions import db
from models import CartItem, Payment, now


class StockError(Exception):
    pass


def cart_summary(user_id):
    items = (CartItem.query.filter_by(user_id=user_id)
             .order_by(CartItem.added_at.desc()).all())
    subtotal = sum((i.line_total for i in items), Decimal("0.00"))
    cfg = current_app.config
    if subtotal == 0 or subtotal >= cfg["FREE_SHIPPING_ABOVE"]:
        shipping = Decimal("0.00")
    else:
        shipping = Decimal(cfg["SHIPPING_FEE"]).quantize(Decimal("0.01"))
    return items, subtotal, shipping, subtotal + shipping


def check_stock(lines):
    """lines: iterable of objects with .product and .quantity"""
    for line in lines:
        p = line.product
        if not p.is_active:
            raise StockError(f"{p.name} is no longer available.")
        if p.stock < line.quantity:
            raise StockError(f"Only {p.stock} left of {p.name}.")


def confirm_order(order):
    """Reserve stock, mark the order Placed and clear those items from the cart."""
    check_stock(order.items)
    for it in order.items:
        it.product.stock -= it.quantity
    order.status = "Placed"
    product_ids = [it.product_id for it in order.items]
    CartItem.query.filter(CartItem.user_id == order.user_id,
                          CartItem.product_id.in_(product_ids)).delete(synchronize_session=False)


def cancel_order(order):
    """Cancel an order and put its stock back if it was already reserved."""
    if order.status == "Placed":
        for it in order.items:
            it.product.stock += it.quantity
    pay = order.payment
    if pay:
        if pay.status == "Success":
            pay.status = "Refund Initiated"
        elif pay.status in ("Created", "Pending", "Failed"):
            pay.status = "Cancelled"
    order.status = "Cancelled"
    order.cancelled_at = now()


def advance_order(order, new_status):
    """Admin status changes. Returns an error message or None."""
    allowed = {"Placed": ["Shipped", "Cancelled"], "Shipped": ["Delivered"]}
    if new_status not in allowed.get(order.status, []):
        return f"An order that is {order.status} cannot be moved to {new_status}."
    if new_status == "Cancelled":
        cancel_order(order)
    elif new_status == "Shipped":
        order.status, order.shipped_at = "Shipped", now()
    elif new_status == "Delivered":
        order.status, order.delivered_at = "Delivered", now()
        pay = order.payment
        if pay and pay.method == "COD" and pay.status == "Pending":
            pay.status, pay.paid_at = "Success", now()
    return None


def new_payment(order, method, status):
    pay = Payment(order=order, amount=order.total_amount, method=method, status=status)
    db.session.add(pay)
    return pay
