"""Functional tests (Chapter: Testing). Run with:  pytest -q"""
import os
import sys
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from config import TestConfig  # noqa: E402
from extensions import db  # noqa: E402
from models import CartItem, Category, Order, Product, Review, User  # noqa: E402


@pytest.fixture()
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        admin = User(name="Admin", email="admin@test.com", role="admin")
        admin.set_password("admin123")
        cat = Category(category_name="Electronics")
        db.session.add_all([admin, cat])
        db.session.flush()
        db.session.add_all([
            Product(name="Earbuds", price=Decimal("1499.00"), stock=5, category_id=cat.category_id),
            Product(name="Cable", price=Decimal("199.00"), stock=10, category_id=cat.category_id),
        ])
        db.session.commit()
    # Yield outside the context so every request gets its own app context
    # and database session, exactly like a real server.
    yield app
    with app.app_context():
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def register(client, email="ravi@test.com"):
    return client.post("/register", data={"name": "Ravi Kumar", "email": email, "phone": "9876543210",
                                          "password": "secret1", "confirm": "secret1"},
                       follow_redirects=True)


def login(client, email, pw):
    return client.post("/login", data={"email": email, "password": pw}, follow_redirects=True)


ADDRESS = {"ship_name": "Ravi Kumar", "ship_phone": "9876543210", "ship_address": "12 MG Road, Worli",
           "ship_city": "Mumbai", "ship_pincode": "400018"}


def test_public_pages_load(client):
    for url in ["/", "/shop", "/shop?q=ear", "/shop?sort=price_desc&min=100&max=2000", "/product/1",
                "/login", "/register"]:
        assert client.get(url).status_code == 200, url
    assert client.get("/product/999").status_code == 404


def test_register_and_duplicate_email(client, app):
    assert b"Your account is ready" in register(client).data
    client.post("/logout")
    assert b"already exists" in register(client).data
    with app.app_context():
        assert User.query.filter_by(email="ravi@test.com").count() == 1


def test_wrong_password_rejected(client):
    register(client)
    client.post("/logout")
    assert b"incorrect" in login(client, "ravi@test.com", "nope").data


def test_search_filters(client):
    page = client.get("/shop?q=cable").data
    assert b"Cable" in page and b"Earbuds" not in page


def test_cart_respects_stock(client, app):
    register(client)
    client.post("/cart/add/1", data={"quantity": 50})
    with app.app_context():
        assert CartItem.query.first().quantity == 5


def test_cod_checkout_reduces_stock_and_clears_cart(client, app):
    register(client)
    client.post("/cart/add/1", data={"quantity": 2})
    r = client.post("/checkout", data={**ADDRESS, "payment_method": "cod"}, follow_redirects=True)
    assert b"placed" in r.data
    with app.app_context():
        order = Order.query.one()
        assert order.status == "Placed"
        assert order.total_amount == Decimal("2998.00")       # free delivery above 499
        assert db.session.get(Product, 1).stock == 3
        assert CartItem.query.count() == 0
        assert order.payment.status == "Pending"


def test_online_payment_demo_success(client, app):
    register(client)
    client.post("/cart/add/2", data={"quantity": 1})
    r = client.post("/checkout", data={**ADDRESS, "payment_method": "online"})
    assert "/pay/" in r.headers["Location"]
    with app.app_context():
        order = Order.query.one()
        assert order.status == "Pending Payment" and order.shipping_fee == Decimal("49.00")
        oid = order.order_id
    client.post(f"/pay/{oid}/demo", data={"outcome": "fail"})
    with app.app_context():
        assert db.session.get(Order, oid).payment.status == "Failed"
    client.post(f"/pay/{oid}/demo", data={"outcome": "success"})
    with app.app_context():
        order = db.session.get(Order, oid)
        assert order.status == "Placed" and order.payment.status == "Success"
        assert db.session.get(Product, 2).stock == 9
    pdf = client.get(f"/pay/invoice/{oid}.pdf")
    assert pdf.status_code == 200 and pdf.data.startswith(b"%PDF")


def test_cancel_restocks(client, app):
    register(client)
    client.post("/cart/add/1", data={"quantity": 1})
    client.post("/checkout", data={**ADDRESS, "payment_method": "cod"})
    client.post("/orders/1/cancel")
    with app.app_context():
        assert db.session.get(Order, 1).status == "Cancelled"
        assert db.session.get(Product, 1).stock == 5


def test_users_cannot_see_others_orders(client, app):
    register(client)
    client.post("/cart/add/1", data={"quantity": 1})
    client.post("/checkout", data={**ADDRESS, "payment_method": "cod"})
    client.post("/logout")
    register(client, email="other@test.com")
    assert client.get("/orders/1").status_code == 404


def test_review_once_per_product(client, app):
    register(client)
    client.post("/product/1/review", data={"rating": 4, "comment": "Good"})
    client.post("/product/1/review", data={"rating": 5, "comment": "Great"})
    with app.app_context():
        assert Review.query.count() == 1 and Review.query.one().rating == 5


def test_admin_area_is_protected(client):
    assert client.get("/admin/").status_code == 302          # not logged in -> login
    register(client)
    assert client.get("/admin/").status_code == 403          # customer


def test_admin_order_workflow_and_pages(client, app):
    register(client)
    client.post("/cart/add/1", data={"quantity": 1})
    client.post("/checkout", data={**ADDRESS, "payment_method": "cod"})
    client.post("/logout")
    login(client, "admin@test.com", "admin123")
    for url in ["/admin/", "/admin/products", "/admin/products/new", "/admin/products/1/edit",
                "/admin/categories", "/admin/orders", "/admin/orders/1", "/admin/users",
                "/admin/reviews", "/admin/reports", "/admin/reports?format=csv"]:
        assert client.get(url).status_code == 200, url
    client.post("/admin/orders/1", data={"status": "Delivered"})        # invalid jump
    with app.app_context():
        assert db.session.get(Order, 1).status == "Placed"
    client.post("/admin/orders/1", data={"status": "Shipped"})
    client.post("/admin/orders/1", data={"status": "Delivered"})
    with app.app_context():
        order = db.session.get(Order, 1)
        assert order.status == "Delivered" and order.payment.status == "Success"


def test_admin_adds_product(client, app):
    login(client, "admin@test.com", "admin123")
    client.post("/admin/products/new", data={"name": "Speaker", "category_id": 1, "price": "999.50",
                                             "stock": "7", "description": "Loud", "is_active": "1"})
    with app.app_context():
        p = Product.query.filter_by(name="Speaker").one()
        assert p.price == Decimal("999.50") and p.stock == 7


def test_blocked_user_cannot_login(client, app):
    register(client)
    client.post("/logout")
    with app.app_context():
        User.query.filter_by(email="ravi@test.com").one().status = "blocked"
        db.session.commit()
    assert b"blocked" in login(client, "ravi@test.com", "secret1").data
