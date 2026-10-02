"""Application configuration.

Values are read from environment variables (or a .env file) so the same code
runs on a laptop with SQLite and on a server with MySQL.
"""
import os
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


class Config:
    STORE_NAME = os.environ.get("STORE_NAME", "Haat")
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-this-secret")

    # MySQL example: mysql+pymysql://root:password@localhost:3306/haat_db
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(BASE_DIR, "instance", "haat.db"),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # Payment gateway (Razorpay). Leave blank to use the built-in demo gateway.
    RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
    RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")

    # Shipping rules (in rupees)
    FREE_SHIPPING_ABOVE = int(os.environ.get("FREE_SHIPPING_ABOVE", 499))
    SHIPPING_FEE = int(os.environ.get("SHIPPING_FEE", 49))
    LOW_STOCK_LIMIT = 5

    # Product image uploads
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
    MAX_CONTENT_LENGTH = 4 * 1024 * 1024  # 4 MB
    ALLOWED_IMAGE_EXT = {"png", "jpg", "jpeg", "webp"}

    # Optional e-mail notifications. If MAIL_SERVER is blank, mails are logged.
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_FROM = os.environ.get("MAIL_FROM", "orders@haat.local")

    CSRF_ENABLED = True
    PRODUCTS_PER_PAGE = 12


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    CSRF_ENABLED = False
    RAZORPAY_KEY_ID = ""
    RAZORPAY_KEY_SECRET = ""
