import os
import json
import unittest
from unittest.mock import patch, MagicMock

os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "admin123"

from server import app


class TestSecurityAndAdmin(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.client.testing = True
        self.token = self._login()

    def _login(self):
        response = self.client.post(
            "/auth/login",
            data=json.dumps({"username": "admin", "password": "admin123"}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        return response.get_json()["token"]

    def _auth_headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    def test_requires_auth_for_admin_status(self):
        response = self.client.get("/admin/status")
        self.assertEqual(response.status_code, 401)

    def test_auth_me(self):
        response = self.client.get("/auth/me", headers=self._auth_headers())
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["username"], "admin")

    def test_api_prefixed_auth_routes(self):
        login_response = self.client.post(
            "/api/auth/login",
            data=json.dumps({"username": "admin", "password": "admin123"}),
            content_type="application/json"
        )
        self.assertEqual(login_response.status_code, 200)
        token = login_response.get_json()["token"]
        me_response = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.get_json()["username"], "admin")

    def test_admin_stats_authenticated(self):
        response = self.client.get("/admin/stats?days=30", headers=self._auth_headers())
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertIn("total_revenue", body)
        self.assertIn("recent_orders", body)

    def test_connector_event_ingestion(self):
        response = self.client.post(
            "/connector/events",
            headers=self._auth_headers(),
            data=json.dumps({"type": "heartbeat", "payload": {"source": "test"}}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        cache_response = self.client.get("/connector/cache", headers=self._auth_headers())
        self.assertEqual(cache_response.status_code, 200)
        self.assertIn("items", cache_response.get_json())

    @patch("server.requests.Session.post")
    def test_create_payment_validation_and_gateway_mock(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "id": "bill_test_1",
                "url": "https://example.com/pay/bill_test_1"
            }
        }
        mock_post.return_value = mock_response
        payload = {
            "nickname": "Player123",
            "email": "player@example.com",
            "cpf": "12345678901",
            "product": "LORD",
            "cellphone": "11999999999"
        }
        response = self.client.post("/create-payment", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("url", response.get_json())


if __name__ == "__main__":
    unittest.main()
