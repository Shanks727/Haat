"""Haat – E-Commerce Website (Flask application factory).

Run:  python app.py        (after `python seed.py` once)
"""
import logging
import os
import secrets
import warnings
from logging.handlers import RotatingFileHandler

from flask import Flask, abort, render_template, request, session
from flask_login import current_user
from sqlalchemy import exc as sa_exc

from config import Config
from extensions import db, login_manager
from models import CartItem, Category, User, WishlistItem
from utils.helpers import money, page_url, tile_colour

# SQLite stores NUMERIC as float; harmless for development.
warnings.filterwarnings("ignore", category=sa_exc.SAWarning, message=".*Decimal.*")


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(os.path.join(app.root_path, "instance"), exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    _setup_logging(app)

    # ---- Modules (see Backend Architecture diagram) -------------------------
    from modules.auth import bp as auth_bp            # 1. Auth module
    from modules.products import bp as products_bp    # 2. Product module
    from modules.cart import bp as cart_bp            # 3. Cart & Order module
    from modules.payment import bp as payment_bp      # 4. Payment module
    from modules.admin import bp as admin_bp          # 5. Admin module
    from modules.reviews import bp as reviews_bp      # 6. Review module

    for blueprint in (auth_bp, products_bp, cart_bp, payment_bp, admin_bp, reviews_bp):
        app.register_blueprint(blueprint)

    _register_middleware(app)
    _register_template_helpers(app)
    _register_error_handlers(app)

    @app.cli.command("init-db")
    def init_db():
        """Create all tables (use seed.py for sample data)."""
        db.create_all()
        print("Tables created.")

    return app


@login_manager.user_loader
def load_user(user_id):
    user = db.session.get(User, int(user_id))
    return user if user and user.is_active else None


# ---- Middleware layer: CSRF validation, request logging ---------------------
def _csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return session["_csrf"]


def _register_middleware(app):
    @app.before_request
    def csrf_protect():
        if request.method == "POST" and app.config.get("CSRF_ENABLED", True):
            token = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
            if not token or token != session.get("_csrf"):
                app.logger.warning("CSRF check failed on %s", request.path)
                abort(400, description="Your session expired. Reload the page and try again.")

    @app.after_request
    def log_request(response):
        if not request.path.startswith("/static"):
            app.logger.debug("%s %s -> %s", request.method, request.path, response.status_code)
        return response


def _register_template_helpers(app):
    app.jinja_env.globals.update(csrf_token=_csrf_token, page_url=page_url, tile_colour=tile_colour)
    app.jinja_env.filters["money"] = money

    @app.context_processor
    def inject_globals():
        cart_count, wish_ids = 0, set()
        if current_user.is_authenticated:
            cart_count = (db.session.query(db.func.coalesce(db.func.sum(CartItem.quantity), 0))
                          .filter(CartItem.user_id == current_user.user_id).scalar())
            wish_ids = {w.product_id for w in
                        WishlistItem.query.filter_by(user_id=current_user.user_id)}
        return {
            "store_name": app.config["STORE_NAME"],
            "nav_categories": Category.query.order_by(Category.category_name).all(),
            "cart_count": cart_count,
            "wish_ids": wish_ids,
        }


def _register_error_handlers(app):
    def render_error(code, title, message):
        return render_template("errors/error.html", code=code, title=title, message=message), code

    @app.errorhandler(400)
    def bad_request(e):
        return render_error(400, "Request could not be processed", e.description)

    @app.errorhandler(403)
    def forbidden(e):
        return render_error(403, "You don't have access to this page",
                            "This area is for store administrators.")

    @app.errorhandler(404)
    def not_found(e):
        return render_error(404, "Page not found",
                            "The link may be old, or the product was removed.")

    @app.errorhandler(413)
    def too_large(e):
        return render_error(413, "File too large", "Images must be under 4 MB.")

    @app.errorhandler(500)
    def server_error(e):
        db.session.rollback()
        app.logger.exception("Server error")
        return render_error(500, "Something broke on our side",
                            "The error was logged. Try again in a moment.")


def _setup_logging(app):
    if app.testing:
        return
    log_dir = os.path.join(app.root_path, "logs")
    os.makedirs(log_dir, exist_ok=True)
    handler = RotatingFileHandler(os.path.join(log_dir, "app.log"), maxBytes=1_000_000, backupCount=3)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    handler.setLevel(logging.INFO)
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
