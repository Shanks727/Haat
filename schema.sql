-- Haat E-Commerce Website: MySQL schema (generated from models.py)
-- Usage:  mysql -u root -p < schema.sql   (or let `python seed.py` create the tables)

CREATE DATABASE IF NOT EXISTS haat_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE haat_db;

CREATE TABLE IF NOT EXISTS users (
	user_id INTEGER NOT NULL AUTO_INCREMENT, 
	name VARCHAR(100) NOT NULL, 
	email VARCHAR(100) NOT NULL, 
	password VARCHAR(255) NOT NULL, 
	phone VARCHAR(15), 
	`role` VARCHAR(15) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	created_at DATETIME, 
	PRIMARY KEY (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS categories (
	category_id INTEGER NOT NULL AUTO_INCREMENT, 
	category_name VARCHAR(100) NOT NULL, 
	description TEXT, 
	created_at DATETIME, 
	PRIMARY KEY (category_id), 
	UNIQUE (category_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS products (
	product_id INTEGER NOT NULL AUTO_INCREMENT, 
	name VARCHAR(150) NOT NULL, 
	description TEXT, 
	price NUMERIC(10, 2) NOT NULL, 
	stock INTEGER NOT NULL, 
	category_id INTEGER NOT NULL, 
	image VARCHAR(255), 
	is_active BOOL NOT NULL, 
	created_at DATETIME, 
	PRIMARY KEY (product_id), 
	FOREIGN KEY(category_id) REFERENCES categories (category_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS orders (
	order_id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER NOT NULL, 
	order_date DATETIME, 
	status VARCHAR(20) NOT NULL, 
	total_amount NUMERIC(10, 2) NOT NULL, 
	subtotal NUMERIC(10, 2) NOT NULL, 
	shipping_fee NUMERIC(10, 2) NOT NULL, 
	payment_method VARCHAR(30) NOT NULL, 
	ship_name VARCHAR(100) NOT NULL, 
	ship_phone VARCHAR(15) NOT NULL, 
	ship_address VARCHAR(255) NOT NULL, 
	ship_city VARCHAR(60) NOT NULL, 
	ship_pincode VARCHAR(10) NOT NULL, 
	shipped_at DATETIME, 
	delivered_at DATETIME, 
	cancelled_at DATETIME, 
	PRIMARY KEY (order_id), 
	FOREIGN KEY(user_id) REFERENCES users (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS order_items (
	item_id INTEGER NOT NULL AUTO_INCREMENT, 
	order_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	quantity INTEGER NOT NULL, 
	unit_price NUMERIC(10, 2) NOT NULL, 
	PRIMARY KEY (item_id), 
	FOREIGN KEY(order_id) REFERENCES orders (order_id), 
	FOREIGN KEY(product_id) REFERENCES products (product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS payments (
	payment_id INTEGER NOT NULL AUTO_INCREMENT, 
	order_id INTEGER NOT NULL, 
	amount NUMERIC(10, 2) NOT NULL, 
	method VARCHAR(30) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	gateway_order_id VARCHAR(64), 
	gateway_payment_id VARCHAR(64), 
	created_at DATETIME, 
	paid_at DATETIME, 
	PRIMARY KEY (payment_id), 
	FOREIGN KEY(order_id) REFERENCES orders (order_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS reviews (
	review_id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	rating INTEGER NOT NULL, 
	comment TEXT, 
	created_at DATETIME, 
	PRIMARY KEY (review_id), 
	CONSTRAINT uq_review_user_product UNIQUE (user_id, product_id), 
	FOREIGN KEY(user_id) REFERENCES users (user_id), 
	FOREIGN KEY(product_id) REFERENCES products (product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS cart_items (
	cart_item_id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	quantity INTEGER NOT NULL, 
	added_at DATETIME, 
	PRIMARY KEY (cart_item_id), 
	CONSTRAINT uq_cart_user_product UNIQUE (user_id, product_id), 
	FOREIGN KEY(user_id) REFERENCES users (user_id), 
	FOREIGN KEY(product_id) REFERENCES products (product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS wishlist (
	wishlist_id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	created_at DATETIME, 
	PRIMARY KEY (wishlist_id), 
	CONSTRAINT uq_wish_user_product UNIQUE (user_id, product_id), 
	FOREIGN KEY(user_id) REFERENCES users (user_id), 
	FOREIGN KEY(product_id) REFERENCES products (product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Indexes
CREATE UNIQUE INDEX ix_users_email ON users (email);
CREATE INDEX ix_orders_order_date ON orders (order_date);
