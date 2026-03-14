import json
import unittest
from unittest.mock import patch, MagicMock
from server import app


class TestPaymentIntegration(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.valid_payload = {
            "nickname": "TestUser",
            "email": "test@example.com",
            "cpf": "12345678901",
            "cellphone": "5511999999999",
            "product": "LORD"
        }

    def test_missing_fields(self):
        response = self.client.post(
            "/create-payment",
            data=json.dumps({"nickname": "TestUser"}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())

    def test_invalid_product(self):
        payload = dict(self.valid_payload)
        payload["product"] = "INVALID_KIT"
        response = self.client.post("/create-payment", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Produto inválido", response.get_json().get("error", ""))

    @patch("server.requests.Session.post")
    def test_valid_payment_mock(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "id": "bill_test_int_1",
                "url": "https://pay.abacate.com/bill_test_int_1"
            }
        }
        mock_post.return_value = mock_response
        response = self.client.post("/create-payment", data=json.dumps(self.valid_payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("url", data)
        self.assertIn("bill_id", data)

if __name__ == "__main__":
    unittest.main()
