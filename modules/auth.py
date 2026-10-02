"""1. Auth module – register, login, logout, account & password."""
import re

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from extensions import db
from models import Order, User
from utils.helpers import safe_next

bp = Blueprint("auth", __name__)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("products.home"))
    form = request.form
    if request.method == "POST":
        name = form.get("name", "").strip()
        email = form.get("email", "").strip().lower()
        phone = form.get("phone", "").strip()
        pw, pw2 = form.get("password", ""), form.get("confirm", "")
        errors = []
        if len(name) < 2:
            errors.append("Enter your full name.")
        if not EMAIL_RE.match(email):
            errors.append("Enter a valid email address.")
        elif User.query.filter_by(email=email).first():
            errors.append("An account with this email already exists. Log in instead.")
        if phone and not re.fullmatch(r"[6-9]\d{9}", phone):
            errors.append("Phone number must be 10 digits.")
        if len(pw) < 6:
            errors.append("Password must be at least 6 characters.")
        if pw != pw2:
            errors.append("Passwords don't match.")
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            user = User(name=name, email=email, phone=phone or None)
            user.set_password(pw)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash(f"Welcome, {user.name.split()[0]}! Your account is ready.", "success")
            return redirect(url_for("products.home"))
    return render_template("auth/register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("products.home"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(request.form.get("password", "")):
            flash("Email or password is incorrect.", "error")
        elif not user.is_active:
            flash("This account has been blocked. Contact the store for help.", "error")
        else:
            login_user(user, remember=bool(request.form.get("remember")))
            dest = safe_next(request.args.get("next"))
            if not dest:
                dest = url_for("admin.dashboard") if user.is_admin else url_for("products.home")
            return redirect(dest)
    return render_template("auth/login.html")


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You're logged out.", "info")
    return redirect(url_for("products.home"))


@bp.route("/account", methods=["GET", "POST"])
@login_required
def account():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "profile":
            name = request.form.get("name", "").strip()
            phone = request.form.get("phone", "").strip()
            if len(name) < 2:
                flash("Enter your full name.", "error")
            elif phone and not re.fullmatch(r"[6-9]\d{9}", phone):
                flash("Phone number must be 10 digits.", "error")
            else:
                current_user.name, current_user.phone = name, phone or None
                db.session.commit()
                flash("Profile saved.", "success")
        elif action == "password":
            if not current_user.check_password(request.form.get("current", "")):
                flash("Current password is incorrect.", "error")
            elif len(request.form.get("new", "")) < 6:
                flash("New password must be at least 6 characters.", "error")
            else:
                current_user.set_password(request.form["new"])
                db.session.commit()
                flash("Password changed.", "success")
        return redirect(url_for("auth.account"))
    order_count = Order.query.filter_by(user_id=current_user.user_id).count()
    return render_template("auth/account.html", order_count=order_count)
