import unittest
import requests
import json

import random

BASE_URL = "http://localhost:5000"

def generate_cpf():
    def calculate_digit(digits):
        s = sum(d * w for d, w in zip(digits, range(len(digits) + 1, 1, -1)))
        r = (s * 10) % 11
        return 0 if r == 10 else r

    cpf = [random.randint(0, 9) for _ in range(9)]
    cpf.append(calculate_digit(cpf))
    cpf.append(calculate_digit(cpf))
    return "".join(map(str, cpf))

class TestPaymentIntegration(unittest.TestCase):
    def test_missing_fields(self):
        # ... existing ...
        payload = {
            "nickname": "TestUser"
        }
        response = requests.post(f"{BASE_URL}/create-payment", json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_invalid_product(self):
        payload = {
            "nickname": "TestUser",
            "email": "test@example.com",
            "cpf": generate_cpf(),
            "cellphone": "5511999999999",
            "product": "INVALID_KIT"
        }
        response = requests.post(f"{BASE_URL}/create-payment", json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid product", response.json().get("error", ""))

    def test_valid_payment_mock(self):
        # This test uses a production token now, so it creates a real pending bill.
        # We must use a valid CPF.
        valid_cpf = generate_cpf()
        # Format CPF with punctuation if needed? Let's try raw first.
        # valid_cpf_formatted = f"{valid_cpf[:3]}.{valid_cpf[3:6]}.{valid_cpf[6:9]}-{valid_cpf[9:]}"
        
        payload = {
            "nickname": "TestUser",
            "email": "test@example.com",
            "cpf": valid_cpf, 
            "cellphone": "5511999999999",
            "product": "LORD"
        }
        response = requests.post(f"{BASE_URL}/create-payment", json=payload)
        if response.status_code == 200:
            data = response.json()
            self.assertIn("url", data)
            # Check if it's a mock URL or real one
            self.assertTrue("mock" in data.get("url") or "abacatepay.com" in data.get("url"))
        else:
            # If server fails (e.g. 500), fail the test
            self.fail(f"Server returned {response.status_code}: {json.dumps(response.json(), indent=2)}")

if __name__ == "__main__":
    unittest.main()
