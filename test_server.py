import unittest
from unittest.mock import patch, MagicMock
import json
import logging
from server import app

# Disable logging during tests
logging.disable(logging.CRITICAL)

class TestPaymentServer(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True
        self.valid_payload = {
            "nickname": "TestUser",
            "email": "test@example.com",
            "cpf": "12345678901",
            "product": "KIT LORD",
            "cellphone": "11999999999"
        }

    @patch('server.requests.Session.post')
    def test_create_payment_success(self, mock_post):
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "id": "bill_123",
                "url": "https://pay.abacate.com/bill_123"
            }
        }
        mock_post.return_value = mock_response

        response = self.app.post('/create-payment', 
                                 data=json.dumps(self.valid_payload),
                                 content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['url'], "https://pay.abacate.com/bill_123")

    def test_validation_error_missing_field(self):
        payload = self.valid_payload.copy()
        del payload['email']
        
        response = self.app.post('/create-payment', 
                                 data=json.dumps(payload),
                                 content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn("Missing required fields", data['error'])

    def test_validation_error_invalid_product(self):
        payload = self.valid_payload.copy()
        payload['product'] = "INVALID_KIT"
        
        response = self.app.post('/create-payment', 
                                 data=json.dumps(payload),
                                 content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn("Invalid product", data['error'])

    @patch('server.requests.Session.post')
    def test_api_timeout(self, mock_post):
        # Mock timeout
        import requests
        mock_post.side_effect = requests.exceptions.Timeout

        response = self.app.post('/create-payment', 
                                 data=json.dumps(self.valid_payload),
                                 content_type='application/json')
        
        self.assertEqual(response.status_code, 504)
        data = json.loads(response.data)
        self.assertEqual(data['error'], "Payment Gateway Timeout")

    @patch('server.requests.Session.post')
    def test_api_connection_error(self, mock_post):
        # Mock connection error
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError

        response = self.app.post('/create-payment', 
                                 data=json.dumps(self.valid_payload),
                                 content_type='application/json')
        
        self.assertEqual(response.status_code, 503)
        data = json.loads(response.data)
        self.assertEqual(data['error'], "Connection Error")

    @patch('server.requests.Session.post')
    def test_api_error_response(self, mock_post):
        # Mock 500 from API
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"error": "Internal Error", "message": "Something went wrong"}
        mock_post.return_value = mock_response

        response = self.app.post('/create-payment', 
                                 data=json.dumps(self.valid_payload),
                                 content_type='application/json')
        
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.data)
        self.assertEqual(data['error'], "Payment Gateway Error")

if __name__ == '__main__':
    unittest.main()
