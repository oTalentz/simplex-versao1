import sqlite3
import os

DB_NAME = 'simplex.db'

def fix_db():
    if not os.path.exists(DB_NAME):
        print(f"Database {DB_NAME} not found!")
        return

    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check orders table columns
        cursor.execute("PRAGMA table_info(orders)")
        columns = [row["name"] for row in cursor.fetchall()]
        print(f"Current orders columns: {columns}")

        if "delivery_status" not in columns:
            print("Adding delivery_status column...")
            try:
                cursor.execute("ALTER TABLE orders ADD COLUMN delivery_status TEXT DEFAULT 'PENDING'")
                print("Added delivery_status.")
            except Exception as e:
                print(f"Error adding delivery_status: {e}")

        if "coupon_code" not in columns:
            print("Adding coupon_code column...")
            try:
                cursor.execute("ALTER TABLE orders ADD COLUMN coupon_code TEXT")
                print("Added coupon_code.")
            except Exception as e:
                print(f"Error adding coupon_code: {e}")

        if "discount_amount" not in columns:
            print("Adding discount_amount column...")
            try:
                cursor.execute("ALTER TABLE orders ADD COLUMN discount_amount INTEGER DEFAULT 0")
                print("Added discount_amount.")
            except Exception as e:
                print(f"Error adding discount_amount: {e}")

        # Check coupons table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='coupons'")
        if not cursor.fetchone():
            print("Creating coupons table...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS coupons (
                    code TEXT PRIMARY KEY,
                    discount_type TEXT DEFAULT 'PERCENT',
                    discount_value INTEGER DEFAULT 0,
                    max_uses INTEGER DEFAULT -1,
                    used_count INTEGER DEFAULT 0,
                    expires_at TIMESTAMP,
                    min_cart_value INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'ACTIVE',
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                )
            """)
        else:
            print("Coupons table exists.")

        # Check coupon_logs table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='coupon_logs'")
        if not cursor.fetchone():
            print("Creating coupon_logs table...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS coupon_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    coupon_code TEXT,
                    admin_user TEXT,
                    action TEXT,
                    details TEXT,
                    timestamp TIMESTAMP
                )
            """)
        else:
            print("Coupon_logs table exists.")
            
        conn.commit()
        conn.close()
        print("Database fix completed.")

    except Exception as e:
        print(f"Database error: {e}")

if __name__ == "__main__":
    fix_db()
