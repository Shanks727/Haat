"""4. Payment module – Razorpay gateway integration, demo gateway, invoices.

If RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET are set (test keys from the
Razorpay dashboard), real Razorpay Checkout is used. Otherwise a clearly
labelled demo gateway lets the project run fully offline.
"""
import hashlib
import hmac

import requests
from flask import (Blueprint, abort, current_app, flash, make_response, redirect,
                   render_template, request, url_for)
from flask_login import current_user, login_required

from extensions import db
from models import Order, now
from services import StockError, confirm_order
from utils.invoice import build_invoice
from utils.notify import order_status_mail

bp = Blueprint("payment", __name__, url_prefix="/pay")
RAZORPAY_ORDERS_URL = "https://api.razorpay.com/v1/orders"


def gateway_enabled():
    cfg = current_app.config
    return bool(cfg["RAZORPAY_KEY_ID"] and cfg["RAZORPAY_KEY_SECRET"])


def _pending_order(order_id):
    order = db.session.get(Order, order_id)
    if not order or order.user_id != current_user.user_id:
        abort(404)
    return order


def _mark_paid(order, gateway_payment_id, method):
    pay = order.payment
    try:
        confirm_order(order)
    except StockError as e:
        # Paid, but stock ran out meanwhile: cancel and refund.
        pay.status, pay.gateway_payment_id, pay.method = "Refund Initiated", gateway_payment_id, method
        order.status, order.cancelled_at = "Cancelled", now()
        db.session.commit()
        flash(f"{e} Your payment will be refunded.", "error")
        return
    pay.status, pay.paid_at = "Success", now()
    pay.gateway_payment_id, pay.method = gateway_payment_id, method
    db.session.commit()
    order_status_mail(order)
    flash(f"Payment received. Order {order.number} is confirmed.", "success")


@bp.route("/<int:order_id>")
@login_required
def pay(order_id):
    order = _pending_order(order_id)
    if order.status != "Pending Payment":
        return redirect(url_for("cart.order_detail", order_id=order_id))

    rzp_order_id = None
    if gateway_enabled():
        cfg = current_app.config
        try:
            resp = requests.post(
                RAZORPAY_ORDERS_URL,
                auth=(cfg["RAZORPAY_KEY_ID"], cfg["RAZORPAY_KEY_SECRET"]),
                json={"amount": int(order.total_amount * 100), "currency": "INR",
                      "receipt": order.number, "notes": {"order_id": order.order_id}},
                timeout=15)
            resp.raise_for_status()
            rzp_order_id = resp.json()["id"]
            order.payment.gateway_order_id = rzp_order_id
            order.payment.method = "Razorpay"
            db.session.commit()
        except requests.RequestException as e:
            current_app.logger.error("Razorpay order create failed: %s", e)
            flash("The payment gateway didn't respond. Try again, or choose cash on delivery.", "error")
            return redirect(url_for("cart.order_detail", order_id=order_id))

    return render_template("orders/payment.html", order=order, rzp_order_id=rzp_order_id,
                           key_id=current_app.config["RAZORPAY_KEY_ID"],
                           amount_paise=int(order.total_amount * 100))


@bp.route("/<int:order_id>/verify", methods=["POST"])
@login_required
def verify(order_id):
    """Razorpay success callback: verify the HMAC signature before trusting it."""
    order = _pending_order(order_id)
    if order.status != "Pending Payment" or not gateway_enabled():
        abort(400)
    rzp_order_id = request.form.get("razorpay_order_id", "")
    rzp_payment_id = request.form.get("razorpay_payment_id", "")
    signature = request.form.get("razorpay_signature", "")
    expected = hmac.new(current_app.config["RAZORPAY_KEY_SECRET"].encode(),
                        f"{rzp_order_id}|{rzp_payment_id}".encode(),
                        hashlib.sha256).hexdigest()
    if rzp_order_id != order.payment.gateway_order_id or not hmac.compare_digest(expected, signature):
        order.payment.status = "Failed"
        db.session.commit()
        current_app.logger.warning("Bad Razorpay signature for order %s", order.number)
        flash("We couldn't verify this payment. No money was taken by us; try again.", "error")
        return redirect(url_for("payment.pay", order_id=order_id))
    _mark_paid(order, rzp_payment_id, "Razorpay")
    return redirect(url_for("cart.order_detail", order_id=order_id))


@bp.route("/<int:order_id>/failed", methods=["POST"])
@login_required
def failed(order_id):
    order = _pending_order(order_id)
    if order.status == "Pending Payment":
        order.payment.status = "Failed"
        db.session.commit()
    flash(request.form.get("reason") or "Payment failed. You can try again.", "error")
    return redirect(url_for("payment.pay", order_id=order_id))


@bp.route("/<int:order_id>/demo", methods=["POST"])
@login_required
def demo(order_id):
    """Offline demo gateway – only active when no Razorpay keys are configured."""
    if gateway_enabled():
        abort(404)
    order = _pending_order(order_id)
    if order.status != "Pending Payment":
        return redirect(url_for("cart.order_detail", order_id=order_id))
    if request.form.get("outcome") == "success":
        _mark_paid(order, f"demo_{order.number}_{int(now().timestamp())}", "Demo Gateway")
        return redirect(url_for("cart.order_detail", order_id=order_id))
    order.payment.status = "Failed"
    db.session.commit()
    flash("Payment failed (demo). Nothing was charged. Try again.", "error")
    return redirect(url_for("payment.pay", order_id=order_id))


@bp.route("/invoice/<int:order_id>.pdf")
@login_required
def invoice(order_id):
    order = db.session.get(Order, order_id)
    if not order or (order.user_id != current_user.user_id and not current_user.is_admin):
        abort(404)
    if order.status == "Pending Payment":
        flash("The invoice is available once the order is confirmed.", "info")
        return redirect(url_for("cart.order_detail", order_id=order_id))
    resp = make_response(build_invoice(order))
    resp.headers["Content-Type"] = "application/pdf"
    resp.headers["Content-Disposition"] = f'inline; filename="Invoice-{order.number}.pdf"'
    return resp
