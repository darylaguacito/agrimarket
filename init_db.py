"""
Run once to create the SQLite database and seed default data.
Usage: python init_db.py
"""
import sqlite3, bcrypt, os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)) if '__file__' in dir() else os.getcwd(), 'agrimarket.db')

SCHEMA = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name       TEXT    NOT NULL,
    email           TEXT    NOT NULL UNIQUE,
    password_hash   TEXT    NOT NULL,
    role            TEXT    NOT NULL DEFAULT 'buyer' CHECK(role IN ('admin','farmer','buyer','driver')),
    phone           TEXT,
    address         TEXT,
    lat             REAL,
    lng             REAL,
    profile_photo   TEXT,
    is_approved     INTEGER NOT NULL DEFAULT 0,
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT    DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS farmer_profiles (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    farm_name      TEXT    NOT NULL,
    farm_location  TEXT,
    lat            REAL,
    lng            REAL,
    product_type   TEXT,
    valid_id_path  TEXT,
    rating         REAL    DEFAULT 0.0,
    rating_count   INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS driver_profiles (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id          INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    vehicle_type     TEXT,
    license_number   TEXT,
    availability     TEXT DEFAULT 'available' CHECK(availability IN ('available','busy','offline')),
    current_location TEXT
);

CREATE TABLE IF NOT EXISTS categories (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    icon TEXT DEFAULT '🌿'
);

CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    farmer_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    name        TEXT    NOT NULL,
    description TEXT,
    price       REAL    NOT NULL DEFAULT 0,
    quantity    INTEGER NOT NULL DEFAULT 0,
    unit        TEXT    DEFAULT 'kg',
    image_path  TEXT,
    is_featured INTEGER DEFAULT 0,
    status      TEXT    DEFAULT 'active' CHECK(status IN ('active','inactive')),
    created_at  TEXT    DEFAULT (datetime('now','localtime')),
    updated_at  TEXT    DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS cart_items (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    quantity   INTEGER NOT NULL DEFAULT 1,
    created_at TEXT    DEFAULT (datetime('now','localtime')),
    UNIQUE(user_id, product_id)
);

CREATE TABLE IF NOT EXISTS orders (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    buyer_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    farmer_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    driver_id        INTEGER REFERENCES users(id) ON DELETE SET NULL,
    total_amount     REAL    NOT NULL DEFAULT 0,
    payment_method   TEXT    DEFAULT 'cod' CHECK(payment_method IN ('cod','online')),
    payment_status   TEXT    DEFAULT 'pending' CHECK(payment_status IN ('pending','paid','failed')),
    shipping_address TEXT    NOT NULL,
    contact_number   TEXT    NOT NULL,
    buyer_lat        REAL,
    buyer_lng        REAL,
    status           TEXT    DEFAULT 'pending'
                     CHECK(status IN ('pending','confirmed','packed','shipped','delivered','cancelled')),
    estimated_delivery TEXT,
    notes            TEXT,
    cancelled_reason TEXT,
    delivery_proof   TEXT,
    created_at       TEXT    DEFAULT (datetime('now','localtime')),
    updated_at       TEXT    DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS order_items (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id   INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    quantity   INTEGER NOT NULL,
    price      REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS order_tracking (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id   INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    status     TEXT    NOT NULL,
    note       TEXT,
    updated_by INTEGER,
    created_at TEXT    DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS notifications (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title            TEXT    NOT NULL,
    message          TEXT    NOT NULL,
    type             TEXT    DEFAULT 'info',
    is_read          INTEGER DEFAULT 0,
    related_order_id INTEGER,
    created_at       TEXT    DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS reviews (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id   INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    buyer_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    farmer_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    rating     INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
    comment    TEXT,
    created_at TEXT    DEFAULT (datetime('now','localtime')),
    UNIQUE(order_id, buyer_id)
);

CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id    INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    sender_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    receiver_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    body        TEXT    NOT NULL,
    is_read     INTEGER DEFAULT 0,
    created_at  TEXT    DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_messages_order ON messages(order_id);
CREATE INDEX IF NOT EXISTS idx_messages_receiver ON messages(receiver_id, is_read);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_products_farmer   ON products(farmer_id);
CREATE INDEX IF NOT EXISTS idx_orders_buyer      ON orders(buyer_id);
CREATE INDEX IF NOT EXISTS idx_orders_farmer     ON orders(farmer_id);
CREATE INDEX IF NOT EXISTS idx_orders_driver     ON orders(driver_id);
CREATE INDEX IF NOT EXISTS idx_orders_status     ON orders(status);
CREATE INDEX IF NOT EXISTS idx_notif_user        ON notifications(user_id, is_read);
"""

CATEGORIES = [
    ('Vegetables','🥦'),('Fruits','🍎'),('Grains','🌾'),
    ('Livestock','🐄'),('Dairy','🥛'),('Herbs','🌿'),
    ('Fertilizers','🧪'),('Seeds','🌱'),('Tools','🔧'),
]

SAMPLE_PRODUCTS = [
    ('Organic Compost Fertilizer','Premium organic compost','Fertilizers',450,500,'kg'),
    ('Vermicompost','High-quality worm castings','Fertilizers',550,300,'kg'),
    ('Urea Fertilizer (46-0-0)','High nitrogen fertilizer','Fertilizers',1250,1000,'kg'),
    ('Glyphosate Herbicide','Non-selective herbicide','Fertilizers',680,250,'liter'),
    ('Rice Seeds - NSIC Rc222','High-yielding rice variety','Seeds',85,2000,'kg'),
    ('Hybrid Rice Seeds','High-performance hybrid rice','Seeds',150,800,'kg'),
    ('Yellow Corn Seeds','High-quality yellow corn seeds','Seeds',120,1000,'kg'),
    ('Tomato Seeds - Hybrid','Disease-resistant hybrid tomato','Seeds',450,50,'kg'),
    ('Eggplant Seeds','High-yielding eggplant variety','Seeds',380,40,'kg'),
    ('Cabbage Seeds','Premium cabbage seeds','Seeds',420,45,'kg'),
    ('Agricultural Lime','Calcium carbonate for soil pH','Fertilizers',280,1000,'kg'),
    ('Cypermethrin Insecticide','Broad-spectrum insecticide','Fertilizers',850,200,'liter'),
]

def init():
    if os.path.exists(DB_PATH):
        print(f"Database already exists at {DB_PATH}")
        ans = input("Re-initialize? This will DELETE all data. (yes/no): ").strip().lower()
        if ans != 'yes':
            print("Aborted.")
            return
        os.remove(DB_PATH)

    db = sqlite3.connect(DB_PATH)
    db.executescript(SCHEMA)

    # Categories
    for name, icon in CATEGORIES:
        db.execute("INSERT OR IGNORE INTO categories (name,icon) VALUES (?,?)", (name, icon))

    # Admin user
    pw = bcrypt.hashpw(b'admin123', bcrypt.gensalt()).decode()
    db.execute(
        "INSERT OR IGNORE INTO users (full_name,email,password_hash,role,is_approved,is_active) "
        "VALUES (?,?,?,?,?,?)",
        ('System Admin', 'admin@agrimarket.com', pw, 'admin', 1, 1)
    )
    db.commit()

    # Get admin id
    admin_id = db.execute("SELECT id FROM users WHERE email='admin@agrimarket.com'").fetchone()[0]

    # Sample products
    for name, desc, cat_name, price, qty, unit in SAMPLE_PRODUCTS:
        cat = db.execute("SELECT id FROM categories WHERE name=?", (cat_name,)).fetchone()
        cat_id = cat[0] if cat else None
        db.execute(
            "INSERT INTO products (farmer_id,category_id,name,description,price,quantity,unit,status) "
            "VALUES (?,?,?,?,?,?,?,'active')",
            (admin_id, cat_id, name, desc, price, qty, unit)
        )

    db.commit()
    db.close()
    print(f"✅ Database created: {DB_PATH}")
    print("   Admin login: admin@agrimarket.com / admin123")

if __name__ == '__main__':
    init()
