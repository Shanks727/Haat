"""Create tables and load sample data.

    python seed.py          # create tables + sample data (skips if data exists)
    python seed.py --reset  # drop everything and start fresh
"""
import random
import sys
from datetime import datetime, timedelta
from decimal import Decimal

from app import create_app
from extensions import db
from models import Category, Order, OrderItem, Payment, Product, Review, User

CATALOGUE = {
    ("Groceries", "Staples, snacks and drinks for the home kitchen."): [
        ("Basmati Rice Premium 5 kg", 649, 40, "Long-grain aged basmati that cooks fluffy and separate. Ideal for biryani and pulao."),
        ("Cold-Pressed Groundnut Oil 1 L", 289, 35, "Wood-pressed groundnut oil with a natural nutty aroma. No chemicals or preservatives."),
        ("Masala Chai Tea 500 g", 245, 50, "Strong Assam CTC blended with cardamom, ginger and clove."),
        ("Roasted Makhana 200 g", 199, 4, "Crunchy fox nuts roasted in olive oil with Himalayan salt."),
        ("Organic Toor Dal 1 kg", 179, 60, "Unpolished pigeon peas, sourced from farms in Karnataka."),
    ],
    ("Electronics", "Audio, charging and everyday gadgets."): [
        ("Wireless Earbuds with ENC", 1499, 25, "Bluetooth 5.3 earbuds with environmental noise cancellation and 30 hours of total playback."),
        ("20000 mAh Power Bank", 1299, 18, "Fast-charging power bank with USB-C PD 22.5W, charges two devices at once."),
        ("Smart LED Bulb 9W", 399, 3, "Wi-Fi bulb with 16 million colours. Works with Alexa and Google Assistant."),
        ("USB-C Fast Charger 33W", 799, 30, "Compact GaN charger that safely fast-charges phones and tablets."),
        ("Mechanical Keyboard TKL", 2999, 0, "Tenkeyless keyboard with hot-swappable brown switches and white backlight."),
    ],
    ("Home & Kitchen", "Cookware, storage and home basics."): [
        ("Stainless Steel Pressure Cooker 3 L", 1849, 15, "Tri-ply base cooker that works on gas and induction. ISI certified."),
        ("Cotton Bedsheet Double", 899, 22, "180 TC pure cotton bedsheet with two pillow covers, block-print design."),
        ("Glass Storage Jars Set of 4", 699, 28, "Airtight borosilicate jars with bamboo lids for dals, spices and snacks."),
        ("Non-stick Tawa 28 cm", 549, 2, "Granite-coated dosa tawa with a cool-touch handle."),
    ],
    ("Books & Stationery", "Books, notebooks and desk supplies."): [
        ("A5 Dotted Notebook", 249, 80, "160 pages of 100 GSM paper that doesn't bleed. Lay-flat binding."),
        ("Gel Pen Pack of 10", 120, 100, "Smooth 0.5 mm gel pens in black and blue."),
        ("The Psychology of Money", 299, 20, "Timeless lessons on wealth, greed and happiness by Morgan Housel."),
        ("Atomic Habits", 399, 26, "An easy and proven way to build good habits and break bad ones, by James Clear."),
    ],
    ("Fashion", "Everyday clothing and accessories."): [
        ("Men's Cotton Kurta", 799, 30, "Breathable cotton kurta with a mandarin collar. Regular fit."),
        ("Women's Printed Dupatta", 449, 24, "Soft mul-cotton dupatta with hand-block floral prints."),
        ("Canvas Sneakers", 1199, 12, "Lightweight everyday sneakers with a cushioned insole."),
        ("Analog Steel Watch", 1599, 5, "Minimal steel watch with a mesh strap and 3 ATM water resistance."),
    ],
    ("Sports & Fitness", "Gear for home workouts and outdoor play."): [
        ("Yoga Mat 6 mm", 599, 40, "Anti-skid TPE yoga mat with carry strap."),
        ("Adjustable Dumbbells 10 kg Pair", 1899, 8, "PVC dumbbell set with removable plates and rods."),
        ("Cricket Tennis Ball Pack of 6", 299, 50, "Heavy tennis balls for gully cricket."),
        ("Insulated Steel Bottle 1 L", 699, 35, "Keeps drinks cold for 24 hours and hot for 12."),
    ],
}

CUSTOMERS = [("Aarav Mehta", "aarav@example.com"), ("Priya Nair", "priya@example.com"),
             ("Rohan Kulkarni", "rohan@example.com"), ("Sneha Iyer", "sneha@example.com"),
             ("Kabir Shah", "kabir@example.com"), ("Ananya Rao", "ananya@example.com")]
CITIES = [("Mumbai", "400018"), ("Pune", "411001"), ("Thane", "400601"), ("Bengaluru", "560001")]
COMMENTS = {5: ["Excellent quality, exactly as described.", "Fast delivery and well packed.", "Worth every rupee."],
            4: ["Good product, slightly pricey.", "Works well. Packaging could be better."],
            3: ["Average. Does the job.", "Okay for the price."],
            2: ["Expected better quality."], 1: ["Stopped working in a week."]}


def run(reset=False):
    app = create_app()
    with app.app_context():
        if reset:
            db.drop_all()
        db.create_all()
        if User.query.first():
            print("Data already present. Use --reset to start fresh.")
            return
        random.seed(7)

        admin = User(name="Admin", email="admin@haat.local", role="admin", phone="9820000000")
        admin.set_password("admin123")
        demo = User(name="Demo Customer", email="demo@haat.local", phone="9876543210")
        demo.set_password("demo123")
        db.session.add_all([admin, demo])
        customers = [demo]
        for name, email in CUSTOMERS:
            u = User(name=name, email=email, phone=f"98{random.randint(10000000, 99999999)}")
            u.set_password("password")
            u.created_at = datetime.now() - timedelta(days=random.randint(20, 120))
            customers.append(u)
            db.session.add(u)

        products = []
        for (cat_name, cat_desc), items in CATALOGUE.items():
            cat = Category(category_name=cat_name, description=cat_desc)
            db.session.add(cat)
            for i, (name, price, stock, desc) in enumerate(items):
                p = Product(name=name, price=Decimal(price), stock=stock, description=desc, category=cat,
                            created_at=datetime.now() - timedelta(days=random.randint(0, 60), minutes=i))
                products.append(p)
                db.session.add(p)
        db.session.flush()

        # ~45 historical orders spread over the last 30 days
        for _ in range(45):
            user = random.choice(customers)
            picks = random.sample([p for p in products if p.price < 2500], random.randint(1, 3))
            when = datetime.now() - timedelta(days=random.randint(0, 29), hours=random.randint(0, 12))
            subtotal = sum((p.price * q for p, q in [(p, 1) for p in picks]), Decimal("0"))
            shipping = Decimal("0") if subtotal >= 499 else Decimal("49")
            city, pin = random.choice(CITIES)
            age = (datetime.now() - when).days
            status = "Delivered" if age >= 4 else ("Shipped" if age >= 1 else "Placed")
            if random.random() < .08:
                status = "Cancelled"
            cod = random.random() < .3
            o = Order(user=user, order_date=when, status=status, subtotal=subtotal, shipping_fee=shipping,
                      total_amount=subtotal + shipping, payment_method="COD" if cod else "Online",
                      ship_name=user.name, ship_phone=user.phone, ship_address="12, Sample Residency, Main Road",
                      ship_city=city, ship_pincode=pin)
            for p in picks:
                o.items.append(OrderItem(product=p, quantity=1, unit_price=p.price))
            if status in ("Shipped", "Delivered"):
                o.shipped_at = when + timedelta(days=1)
            if status == "Delivered":
                o.delivered_at = when + timedelta(days=3)
            if status == "Cancelled":
                o.cancelled_at = when + timedelta(hours=5)
            if cod:
                pstatus = "Success" if status == "Delivered" else ("Cancelled" if status == "Cancelled" else "Pending")
                pay = Payment(amount=o.total_amount, method="COD", status=pstatus,
                              paid_at=o.delivered_at if pstatus == "Success" else None)
            else:
                pay = Payment(amount=o.total_amount, method="Demo Gateway",
                              status="Refund Initiated" if status == "Cancelled" else "Success",
                              paid_at=when, gateway_payment_id=f"demo_seed_{random.randint(10**6, 10**7)}")
            o.payments.append(pay)
            db.session.add(o)

            if status == "Delivered" and random.random() < .7:
                for p in picks:
                    if not Review.query.filter_by(user_id=user.user_id, product_id=p.product_id).first() \
                            and not any(r.user is user and r.product is p for r in db.session.new if isinstance(r, Review)):
                        rating = random.choices([5, 4, 3, 2, 1], weights=[45, 30, 13, 7, 5])[0]
                        db.session.add(Review(user=user, product=p, rating=rating,
                                              comment=random.choice(COMMENTS[rating]),
                                              created_at=min(o.delivered_at + timedelta(days=1), datetime.now())))
            db.session.flush()

        db.session.commit()
        print(f"Seeded {len(products)} products, {Category.query.count()} categories, "
              f"{User.query.count()} users, {Order.query.count()} orders, {Review.query.count()} reviews.")
        print("Admin:    admin@haat.local / admin123")
        print("Customer: demo@haat.local  / demo123")


if __name__ == "__main__":
    run(reset="--reset" in sys.argv)
