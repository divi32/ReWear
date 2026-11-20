"""
=============================================================================
database.py - SQLite Database Setup and Management for ReWear
=============================================================================
This module handles:
1. Connecting to the SQLite database ('rewear.db').
2. Creating the 5 core relational tables (users, products, wishlist, orders, order_items).
3. Parameterized query helper functions (? placeholders) to prevent SQL injection.
4. Auto-seeding default demo accounts (admin, seller, buyer) and 8 sample clothes
   with Pillow-generated clean placeholder images so the demo is ready on first run.
=============================================================================
"""

import os
import sqlite3
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

# Path definitions
DB_NAME = "rewear.db"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, DB_NAME)
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")


def get_connection():
    """
    Establish and return a connection to the SQLite database.
    Enables foreign key constraints and sets row_factory for dict-like access.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn


def execute_query(query, params=()):
    """
    Execute an INSERT, UPDATE, or DELETE query using parameterized inputs.
    Returns the last inserted row ID.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        last_id = cursor.lastrowid
        return last_id
    finally:
        conn.close()


def fetch_all(query, params=()):
    """
    Execute a SELECT query with parameters and return all rows as a list of dictionaries.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def fetch_one(query, params=()):
    """
    Execute a SELECT query with parameters and return the first row as a dictionary or None.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_sample_placeholder_image(filename, title, category, bg_color, accent_color):
    """
    Creates a clean, attractive placeholder image using Pillow.
    Ensures the demo has functional clothing images without any external internet dependency.
    """
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    filepath = os.path.join(UPLOADS_DIR, filename)

    # Return if image already exists
    if os.path.exists(filepath):
        return filepath

    # Dimensions: 600 x 600 px
    img = Image.new("RGB", (600, 600), color=bg_color)
    draw = ImageDraw.Draw(img)

    # Draw rounded-corner style card border
    draw.rectangle([20, 20, 580, 580], outline=accent_color, width=4)
    draw.rectangle([30, 30, 570, 570], outline="#E0E0E0", width=1)

    # Draw top banner badge
    draw.rectangle([40, 45, 560, 95], fill=accent_color)
    draw.text((210, 60), "ReWear ♻️ Eco Choice", fill="white")

    # Draw central decorative clothing silhouette box
    draw.rectangle([140, 150, 460, 380], fill="#FFFFFF", outline=accent_color, width=2)
    draw.text((250, 240), f"[{category.upper()}]", fill=accent_color)
    draw.text((200, 275), "Pre-Loved Fashion", fill="#555555")

    # Draw bottom title card
    draw.rectangle([40, 430, 560, 540], fill="#FFFFFF", outline="#DDDDDD", width=1)
    draw.text((60, 455), title[:35], fill="#222222")
    draw.text((60, 490), f"Category: {category}  •  Condition: Excellent", fill="#666666")

    # Save resized and optimized image
    img.save(filepath, format="JPEG", quality=90)
    return filepath


def init_db():
    """
    Initializes the SQLite database:
    1. Creates the uploads/ folder if missing.
    2. Creates the 5 required relational tables.
    3. Seeds default demo users and sample clothes if the tables are empty.
    """
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    conn = get_connection()
    cursor = conn.cursor()

    # Table 1: users
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('buyer', 'seller', 'admin')),
        upi_id TEXT
    );
    """)

    # Table 2: products
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        product_id INTEGER PRIMARY KEY AUTOINCREMENT,
        seller_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        category TEXT NOT NULL,
        size TEXT NOT NULL,
        price REAL NOT NULL CHECK(price > 0),
        image_path TEXT,
        status TEXT NOT NULL DEFAULT 'available' CHECK(status IN ('available', 'sold')),
        FOREIGN KEY (seller_id) REFERENCES users (user_id) ON DELETE CASCADE
    );
    """)

    # Table 3: wishlist
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS wishlist (
        wishlist_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        UNIQUE(user_id, product_id),
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products (product_id) ON DELETE CASCADE
    );
    """)

    # Table 4: orders
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        order_id INTEGER PRIMARY KEY AUTOINCREMENT,
        buyer_id INTEGER NOT NULL,
        total_amount REAL NOT NULL,
        payment_method TEXT NOT NULL DEFAULT 'Cash on Delivery',
        status TEXT NOT NULL DEFAULT 'completed',
        created_at TEXT NOT NULL,
        FOREIGN KEY (buyer_id) REFERENCES users (user_id) ON DELETE CASCADE
    );
    """)

    # Table 5: order_items
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_items (
        item_id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 1,
        price REAL NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders (order_id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products (product_id) ON DELETE CASCADE
    );
    """)

    # Table 6: donations
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS donations (
        donation_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        type TEXT NOT NULL,
        quantity INTEGER NOT NULL CHECK(quantity > 0),
        condition TEXT NOT NULL CHECK(condition IN ('Wearable but donating', 'Not wearable - for recycling')),
        city TEXT NOT NULL,
        contact TEXT NOT NULL,
        image_path TEXT,
        status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending', 'Collected')),
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
    );
    """)

    # Migrations for existing databases: ensure new columns exist safely
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN upi_id TEXT;")
    except Exception:
        pass  # Column already exists

    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN payment_method TEXT DEFAULT 'Cash on Delivery';")
    except Exception:
        pass  # Column already exists

    conn.commit()
    conn.close()

    # Seed sample users and products if database is fresh
    seed_sample_data()

    # Always ensure admin@rewear.com exists with Admin@123 across all restarts and deployments
    ensure_admin_account()


def ensure_admin_account():
    """
    Guarantees that the default admin account (admin@rewear.com / Admin@123)
    always exists with the 'admin' role and valid PBKDF2 hashed password.
    Runs on every app launch:
    - If admin@rewear.com is missing -> creates it.
    - If admin@rewear.com exists -> unconditionally resets its password to 'Admin@123'
      and ensures its role is 'admin'.
    """
    from auth import hash_password

    new_hash = hash_password("Admin@123")
    admin = fetch_one("SELECT user_id FROM users WHERE email = ?", ("admin@rewear.com",))
    
    if not admin:
        execute_query(
            "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
            ("Admin ReWear", "admin@rewear.com", new_hash, "admin")
        )
    else:
        execute_query(
            "UPDATE users SET password_hash = ?, role = 'admin' WHERE email = ?",
            (new_hash, "admin@rewear.com")
        )

    # Ensure default demo seller has a sample UPI ID for testing direct UPI payments
    seller = fetch_one("SELECT user_id, upi_id FROM users WHERE email = ?", ("seller@rewear.com",))
    if seller and not seller.get("upi_id"):
        execute_query("UPDATE users SET upi_id = ? WHERE email = ?", ("priya.ecostore@okaxis", "seller@rewear.com"))


def seed_sample_data():
    """
    Seeds the database with 3 demo accounts (admin, seller, buyer)
    and 8 pre-populated sample clothes listings with Pillow placeholder images.
    """
    # Import hashing function from auth to keep PBKDF2 logic unified
    from auth import hash_password

    # Check if users already exist
    existing_users = fetch_all("SELECT user_id FROM users LIMIT 1")
    if existing_users:
        return  # Database already seeded

    # 1. Create Default Users
    # Password for demo accounts:
    # admin@rewear.com -> Admin@123
    # seller@rewear.com -> seller123
    # buyer@rewear.com -> buyer123
    users_data = [
        ("Admin ReWear", "admin@rewear.com", hash_password("Admin@123"), "admin"),
        ("Priya EcoStore", "seller@rewear.com", hash_password("seller123"), "seller"),
        ("Rahul Sharma", "buyer@rewear.com", hash_password("buyer123"), "buyer")
    ]

    for name, email, pwd_hash, role in users_data:
        execute_query(
            "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
            (name, email, pwd_hash, role)
        )

    # Retrieve seller ID
    seller = fetch_one("SELECT user_id FROM users WHERE email = ?", ("seller@rewear.com",))
    seller_id = seller["user_id"] if seller else 1

    # 2. Generate 8 Sample Clothes with Pillow Images
    sample_products = [
        {
            "title": "Vintage Oversized Denim Jacket",
            "category": "Jackets",
            "size": "L",
            "price": 899.00,
            "filename": "sample_denim_jacket.jpg",
            "bg_color": "#F0F4F8",
            "accent_color": "#2B5B84"
        },
        {
            "title": "Floral Summer Cotton Maxi Dress",
            "category": "Dresses",
            "size": "M",
            "price": 649.00,
            "filename": "sample_floral_dress.jpg",
            "bg_color": "#FDF2F4",
            "accent_color": "#C24168"
        },
        {
            "title": "Minimalist Organic Graphic Tee",
            "category": "T-Shirts",
            "size": "M",
            "price": 349.00,
            "filename": "sample_graphic_tee.jpg",
            "bg_color": "#F4F7F5",
            "accent_color": "#2E7D32"
        },
        {
            "title": "Beige Slim Fit Casual Chinos",
            "category": "Bottoms",
            "size": "32",
            "price": 599.00,
            "filename": "sample_beige_chinos.jpg",
            "bg_color": "#FBF7F0",
            "accent_color": "#8D6E63"
        },
        {
            "title": "Warm Cable Knit Wool Sweater",
            "category": "Sweaters",
            "size": "S",
            "price": 749.00,
            "filename": "sample_knit_sweater.jpg",
            "bg_color": "#F5F3FF",
            "accent_color": "#5E35B1"
        },
        {
            "title": "Classic Corduroy Button-Down Shirt",
            "category": "Shirts",
            "size": "XL",
            "price": 499.00,
            "filename": "sample_corduroy_shirt.jpg",
            "bg_color": "#FFF8E1",
            "accent_color": "#E65100"
        },
        {
            "title": "Handcrafted Festive Ethnic Kurta",
            "category": "Ethnic Wear",
            "size": "L",
            "price": 799.00,
            "filename": "sample_ethnic_kurta.jpg",
            "bg_color": "#FFF3E0",
            "accent_color": "#D84315"
        },
        {
            "title": "Sporty Fleece Pullover Hoodie",
            "category": "Hoodies",
            "size": "M",
            "price": 699.00,
            "filename": "sample_fleece_hoodie.jpg",
            "bg_color": "#ECEFF1",
            "accent_color": "#37474F"
        }
    ]

    for item in sample_products:
        # Create image file using Pillow
        image_path = create_sample_placeholder_image(
            filename=item["filename"],
            title=item["title"],
            category=item["category"],
            bg_color=item["bg_color"],
            accent_color=item["accent_color"]
        )

        # Relative path stored in database for portability
        rel_image_path = os.path.join("uploads", item["filename"])

        execute_query(
            """
            INSERT INTO products (seller_id, title, category, size, price, image_path, status)
            VALUES (?, ?, ?, ?, ?, ?, 'available')
            """,
            (seller_id, item["title"], item["category"], item["size"], item["price"], rel_image_path)
        )
