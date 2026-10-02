# Haat – E-Commerce Website

Mini project for T.Y. B.Sc. Computer Science (2025–26). A complete online store built with
**HTML, CSS, JavaScript, Python (Flask) and MySQL**, with Razorpay payment integration and
ReportLab PDF invoices, following the design in the project report.

## Features

**Customer:** register / login, browse the catalogue, search, filter by category, price and stock,
sort by price, newest or rating, product page with stock status, cart (saved to the account),
wishlist, checkout with address validation, online payment (Razorpay) or cash on delivery,
order history, order tracking (Placed → Shipped → Delivered), order cancellation with restock,
PDF invoice download, ratings & reviews with a "verified buyer" badge, profile and password change.

**Admin:** dashboard (revenue, orders waiting to ship, low stock, 14-day sales chart, orders by
status, best sellers), product management with image upload, category management, order
processing with status workflow, customer list with block / unblock, review moderation,
sales report for any date range with category and product breakdown, CSV export.

**Security & middleware:** salted password hashing (Werkzeug), CSRF tokens on every form,
role-based access to `/admin`, Razorpay HMAC-SHA256 signature verification, stock checks
before payment is confirmed, error pages (400/403/404/413/500), request and error logging.

## Quick start (runs in 2 minutes with SQLite)

```bash
cd haat
python -m venv venv
venv\Scripts\activate            # Windows   (macOS/Linux: source venv/bin/activate)
pip install -r requirements.txt
python seed.py                   # creates tables + sample data
python app.py                    # open http://127.0.0.1:5000
```

| Account  | Email              | Password |
|----------|--------------------|----------|
| Admin    | admin@haat.local   | admin123 |
| Customer | demo@haat.local    | demo123  |

Without Razorpay keys, checkout uses a clearly labelled **demo gateway** with
"Pay" and "Simulate a failed payment" buttons, so the full flow works offline for the viva.

## Using MySQL (as specified in the report)

1. Create the database (MySQL Workbench or the command line):
   ```sql
   CREATE DATABASE haat_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```
2. Copy `.env.example` to `.env` and set:
   ```
   DATABASE_URL=mysql+pymysql://root:YOUR_PASSWORD@localhost:3306/haat_db
   ```
3. Run `python seed.py --reset` then `python app.py`.

`schema.sql` contains the equivalent MySQL DDL if you want to create the tables by hand
or include it in the report.

## Real Razorpay payments (test mode)

1. Sign up at razorpay.com, switch to **Test Mode**, then Settings → API Keys → Generate key.
2. Put the keys in `.env` as `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET`, restart the app.
3. Pay with test card `4111 1111 1111 1111` (any future expiry, any CVV) or UPI `success@razorpay`.

Flow: server creates a Razorpay order → Razorpay Checkout opens in the browser → on success
the server verifies the signature `HMAC_SHA256(order_id|payment_id, key_secret)` → stock is
reduced and the order becomes **Placed**. A failed or tampered payment never confirms an order.

## Tests

```bash
pytest -q
```
14 functional tests cover registration, login, search, cart stock limits, COD and online
checkout, failed payments, invoices, cancellation and restock, access control between
customers, admin-only pages, the admin order workflow, adding products, and blocked users.

## How the code maps to the report

| Report section | Where it is |
|---|---|
| Backend modules 1–6 (Ch. 4.2) | `modules/auth.py`, `products.py`, `cart.py`, `payment.py`, `admin.py`, `reviews.py` |
| Middleware layer | `app.py` (CSRF, logging, error handlers), `utils/helpers.py` (`admin_required`) |
| Data schema (Ch. 4.3) | `models.py`, `schema.sql` |
| Invoice PDF service | `utils/invoice.py` (ReportLab) |
| Email/SMS service | `utils/notify.py` (SMTP if configured, otherwise logged) |
| Order rules (stock, cancel, status) | `services.py` |
| Frontend | `templates/` (Jinja2 HTML), `static/css/style.css`, `static/js/main.js` |
| Testing phase | `tests/test_app.py` |

### Schema notes
Tables match the report's schema: `users`, `categories`, `products`, `orders`,
`order_items`, `payments`, `reviews`. Two tables were added for features listed in scope:
`cart_items` (cart saved per user) and `wishlist`. `orders` also stores the delivery address,
subtotal, shipping fee and shipped/delivered/cancelled times for tracking. Admins are
users with `role = 'admin'`, so one login screen serves both actors; this replaces the
separate `admins` table from the diagram.

### Order status lifecycle
`Pending Payment` (online, not yet paid) → `Placed` (paid or COD) → `Shipped` → `Delivered`.
`Pending Payment` and `Placed` orders can be cancelled; cancelling a placed order returns its
stock, and a paid order's payment is marked `Refund Initiated`.

## Project structure

```
haat/
├── app.py              application factory, middleware, error handlers
├── config.py           settings (.env)
├── extensions.py       SQLAlchemy + Flask-Login
├── models.py           database tables
├── services.py         order business rules
├── seed.py             sample data
├── schema.sql          MySQL DDL
├── modules/            auth, products, cart, payment, admin, reviews
├── utils/              helpers, invoice PDF, notifications
├── templates/          storefront, orders, admin, errors
├── static/             css, js, uploads (product photos)
└── tests/              pytest functional tests
```
