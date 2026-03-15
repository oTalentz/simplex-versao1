
import unittest
import json
import sys
import os
import datetime
import tempfile
import sqlite3

# Add parent directory to path to import server
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server
from server import app, init_db, get_db_connection, now_iso

class TestCoupons(unittest.TestCase):
    def setUp(self):
        # Force SQLite
        server.USE_TURSO = False
        # Use a temp db file
        self.db_fd, self.db_path = tempfile.mkstemp()
        server.DB_NAME = self.db_path
        
        # Initialize DB
        with app.app_context():
            init_db()
        
        self.app = app.test_client()
        self.app.testing = True
        
        self.test_code = "TESTCOUPON123"
        self.admin_token = self.get_admin_token()
        
    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def get_admin_token(self):
        # Mock token generation
        # We need to replicate jwt_encode logic or import it
        from server import jwt_encode, JWT_EXP_MINUTES
        import time
        now = int(time.time())
        payload = {
            "sub": "admin",
            "role": "superadmin",
            "iat": now,
            "exp": now + JWT_EXP_MINUTES * 60
        }
        return jwt_encode(payload)

    def create_coupon(self, code, type="PERCENT", value=10, min_cart=0, max_uses=-1, expires=None):
        return self.app.post('/admin/coupons', 
            data=json.dumps({
                "code": code,
                "discount_type": type,
                "discount_value": value,
                "min_cart_value": min_cart,
                "max_uses": max_uses,
                "expires_at": expires,
                "status": "ACTIVE"
            }),
            headers={
                "Authorization": f"Bearer {self.admin_token}",
                "Content-Type": "application/json"
            }
        )

    def test_create_coupon(self):
        # Ensure clean state
        server.DB_NAME = self.db_path
        
        res = self.create_coupon(self.test_code, "PERCENT", 10)
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data.get("code"), self.test_code)

    def test_validate_valid_coupon(self):
        server.DB_NAME = self.db_path
        self.create_coupon(self.test_code, "PERCENT", 10)
        
        res = self.app.post('/api/validate-coupon',
            data=json.dumps({
                "code": self.test_code,
                "product": "LORD" # Assume LORD exists in PRICES
            }),
            headers={"Content-Type": "application/json"}
        )
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data.get("valid"))
        self.assertEqual(data.get("percent"), 10)

    def test_validate_expired_coupon(self):
        server.DB_NAME = self.db_path
        past_date = (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat()
        self.create_coupon(self.test_code, "PERCENT", 10, expires=past_date)
        
        res = self.app.post('/api/validate-coupon',
            data=json.dumps({
                "code": self.test_code,
                "product": "LORD"
            }),
            headers={"Content-Type": "application/json"}
        )
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertFalse(data.get("valid"))
        
    def test_coupon_history(self):
        server.DB_NAME = self.db_path
        # Create
        self.create_coupon(self.test_code, "PERCENT", 10)
        
        # Wait to ensure timestamp difference (since we strip microseconds)
        import time
        time.sleep(1.1)
        
        # Update
        res = self.app.put(f'/admin/coupons/{self.test_code}',
            data=json.dumps({
                "discount_value": 20,
                "status": "ACTIVE"
            }),
            headers={
                "Authorization": f"Bearer {self.admin_token}",
                "Content-Type": "application/json"
            }
        )
        self.assertEqual(res.status_code, 200)
        
        # Get Logs
        res = self.app.get(f'/admin/coupons/{self.test_code}/logs',
             headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        self.assertEqual(res.status_code, 200)
        logs = json.loads(res.data)
        self.assertTrue(len(logs) >= 2) # Create + Update
        self.assertEqual(logs[0]["action"], "UPDATE")
        self.assertEqual(logs[-1]["action"], "CREATE")

    def test_coupon_stats(self):
        server.DB_NAME = self.db_path
        # Create a few coupons
        self.create_coupon("COUPON1", "PERCENT", 10)
        self.create_coupon("COUPON2", "FIXED", 500)
        
        # Simulate usage
        conn = sqlite3.connect(self.db_path)
        # Insert paid order with coupon
        conn.execute("INSERT INTO orders (id, status, coupon_code, discount_amount, created_at) VALUES (?, ?, ?, ?, ?)", 
                     ("ORDER1", "PAID", "COUPON1", 500, "2023-01-01T00:00:00"))
        
        # Update coupon usage
        conn.execute("UPDATE coupons SET used_count = 1 WHERE code = 'COUPON1'")
        
        conn.commit()
        conn.close()
        
        # Call stats endpoint
        res = self.app.get('/admin/coupons/stats', 
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        
        self.assertEqual(data["active_coupons"], 2)
        self.assertEqual(data["total_uses"], 1)
        self.assertEqual(data["total_discount_given"], 500)
        self.assertEqual(len(data["top_coupons"]), 2)
        self.assertEqual(data["top_coupons"][0]["code"], "COUPON1")

if __name__ == '__main__':
    unittest.main()
