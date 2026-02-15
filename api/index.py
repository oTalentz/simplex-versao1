import os
import json
import logging
import time
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure Logging (Vercel logs to stdout/stderr automatically, but we keep this structure)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
# Enable CORS for all domains to allow Vercel frontend to talk to Vercel backend
CORS(app)

# Configuration
ABACATE_API_TOKEN = os.getenv("ABACATE_PAY_TOKEN", "abc_prod_0mDdwwz23aySmeUemLQmPhzw")
ABACATE_API_URL = "https://api.abacatepay.com/v1/billing/create"
ABACATE_PIX_URL = "https://api.abacatepay.com/v1/pixQrCode/create"
API_TIMEOUT = int(os.getenv("API_TIMEOUT", 30))  # 30 seconds timeout

# Product Pricing (in cents)
PRICES = {
    "LORD": 4990,
    "KNIGHT": 7990,
    "GUARDIAN": 9990,
    "CHAMPION": 12990
}

# --- Helper Functions ---

def get_requests_session():
    """
    Creates a requests session with retry logic and backoff.
    """
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,  # wait 1s, 2s, 4s...
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

def validate_customer_data(data):
    """
    Validates customer data before sending to API.
    Returns (is_valid, error_message).
    """
    required_fields = ['nickname', 'email', 'cpf', 'product']
    
    # Check for missing fields
    missing = [field for field in required_fields if not data.get(field)]
    if missing:
        return False, f"Missing required fields: {', '.join(missing)}"

    # Validate Product
    product_raw = data.get('product', '')
    product_name = product_raw.replace('KIT', '').strip().upper()
    if product_name not in PRICES:
        return False, f"Invalid product: {product_raw}. Available: {', '.join(PRICES.keys())}"

    # Basic Email Validation
    if '@' not in data.get('email', ''):
        return False, "Invalid email format"

    # Basic CPF Validation (Length)
    cpf_clean = "".join(filter(str.isdigit, str(data.get('cpf', ''))))
    if len(cpf_clean) != 11:
        return False, "CPF must have 11 digits"

    return True, None

def sanitize_phone(phone):
    """
    Sanitizes phone number to format required by Abacate Pay (DDI+DDD+Number).
    Defaults to 5511999999999 if invalid/missing.
    """
    clean = "".join(filter(str.isdigit, str(phone)))
    
    # If empty or too short, return default
    if not clean or len(clean) < 10:
        logger.warning(f"Invalid phone number provided: '{phone}'. Using default.")
        return "5511999999999"
    
    # If 10 or 11 digits (e.g. 11999999999), add Brazil DDI (55)
    if len(clean) in [10, 11]:
        return "55" + clean
        
    return clean

# --- Routes ---

@app.route('/')
@app.route('/api/')
def home():
    return "Simplex Antigravity Payment API is running!"

@app.route('/create-payment', methods=['POST'])
@app.route('/api/create-payment', methods=['POST'])
def create_payment():
    req_id = int(time.time() * 1000)
    logger.info(f"[{req_id}] Received payment creation request")
    
    try:
        data = request.json
        if not data:
            logger.warning(f"[{req_id}] No JSON data provided")
            return jsonify({"error": "No data provided"}), 400

        # 1. Validation
        is_valid, error_msg = validate_customer_data(data)
        if not is_valid:
            logger.warning(f"[{req_id}] Validation failed: {error_msg}")
            return jsonify({"error": error_msg}), 400

        nickname = data.get('nickname')
        email = data.get('email')
        cpf = data.get('cpf')
        product_raw = data.get('product', '')
        cellphone = data.get('cellphone', '')

        product_name = product_raw.replace('KIT', '').strip().upper()
        amount = PRICES.get(product_name)
        
        cellphone_clean = sanitize_phone(cellphone)
        cpf_clean = "".join(filter(str.isdigit, str(cpf)))

        logger.info(f"[{req_id}] Processing payment for {nickname} - {product_name} ({amount} cents)")

        # 2. Prepare Payload
        payload = {
            "frequency": "ONE_TIME",
            "methods": ["PIX"], # API only accepts PIX for now, others cause 422 error
            "products": [
                {
                    "externalId": product_name,
                    "name": f"VIP {product_name}",
                    "quantity": 1,
                    "price": amount,
                    "description": f"VIP {product_name} para o jogador {nickname}"
                }
            ],
            # Vercel deployment URL might need adjustment here for production return URLs
            # For now keeping localhost as default or env var could be better
            "returnUrl": os.getenv("RETURN_URL", "http://localhost:5500/success"),
            "completionUrl": os.getenv("COMPLETION_URL", "http://localhost:5500/success"),
            "customer": {
                "name": nickname, 
                "email": email,
                "taxId": cpf_clean,
                "cellphone": cellphone_clean
            }
        }

        # 3. Send Request with Retries & Timeout
        session = get_requests_session()
        headers = {
            "Authorization": f"Bearer {ABACATE_API_TOKEN}",
            "Content-Type": "application/json"
        }

        logger.debug(f"[{req_id}] Sending payload to Abacate Pay: {json.dumps(payload, indent=2)}")

        response = session.post(
            ABACATE_API_URL, 
            json=payload, 
            headers=headers, 
            timeout=API_TIMEOUT
        )
        
        # 4. Handle Response
        try:
            result = response.json()
        except json.JSONDecodeError:
            logger.error(f"[{req_id}] Failed to decode JSON response: {response.text}")
            return jsonify({"error": "Invalid response from Payment Gateway", "details": response.text}), 502

        if response.status_code != 200:
            error_details = result.get('error') or result
            logger.error(f"[{req_id}] Abacate Pay API Error ({response.status_code}): {json.dumps(error_details)}")
            return jsonify({"error": "Payment Gateway Error", "details": error_details}), response.status_code

        # Log Success
        logger.info(f"[{req_id}] Payment created successfully. Bill ID: {result.get('data', {}).get('id')}")
        
        data_obj = result.get("data")
        if not data_obj or not data_obj.get("url"):
            logger.error(f"[{req_id}] No payment URL in successful response: {json.dumps(result)}")
            return jsonify({"error": "No payment URL returned"}), 500

        return jsonify({"url": data_obj.get("url")})

    except requests.exceptions.Timeout:
        logger.error(f"[{req_id}] Request to Payment Gateway timed out after {API_TIMEOUT}s")
        return jsonify({"error": "Payment Gateway Timeout", "message": "The payment service is taking too long to respond. Please try again."}), 504
    
    except requests.exceptions.ConnectionError:
        logger.error(f"[{req_id}] Connection error to Payment Gateway")
        return jsonify({"error": "Connection Error", "message": "Could not connect to payment service. Please check your internet connection."}), 503
        
    except Exception as e:
        logger.exception(f"[{req_id}] Unexpected server error: {str(e)}")
        return jsonify({"error": "Internal Server Error", "message": "An unexpected error occurred."}), 500

@app.route('/create-pix-payment', methods=['POST'])
@app.route('/api/create-pix-payment', methods=['POST'])
def create_pix_payment():
    req_id = int(time.time() * 1000)
    logger.info(f"[{req_id}] Received PIX creation request")
    
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400

        is_valid, error_msg = validate_customer_data(data)
        if not is_valid:
            return jsonify({"error": error_msg}), 400

        nickname = data.get('nickname')
        email = data.get('email')
        cpf = data.get('cpf')
        product_raw = data.get('product', '')
        cellphone = data.get('cellphone', '')
        
        product_name = product_raw.replace('KIT', '').strip().upper()
        amount = PRICES.get(product_name)
        
        cellphone_clean = sanitize_phone(cellphone)
        cpf_clean = "".join(filter(str.isdigit, str(cpf)))

        payload = {
            "amount": amount,
            "description": f"VIP {product_name} - {nickname}",
            "customer": {
                "name": nickname,
                "email": email,
                "taxId": cpf_clean,
                "cellphone": cellphone_clean
            }
        }

        session = get_requests_session()
        headers = {
            "Authorization": f"Bearer {ABACATE_API_TOKEN}",
            "Content-Type": "application/json"
        }

        response = session.post(
            ABACATE_PIX_URL, 
            json=payload, 
            headers=headers,
            timeout=API_TIMEOUT
        )
        
        if response.status_code != 200:
            logger.error(f"[{req_id}] Abacate Pay PIX Error: {response.text}")
            return jsonify({"error": "Payment Gateway Error", "details": response.json()}), response.status_code

        result = response.json()
        logger.info(f"[{req_id}] Abacate Pay Response: {json.dumps(result)}")
        
        if result.get('success') is False:
             raw_error = result.get('error', 'Unknown error from payment provider')
             
             # Translate common errors
             error_msg = raw_error
             if "taxId" in raw_error:
                 error_msg = "CPF inválido. Verifique se o número está correto."
             elif "email" in raw_error:
                 error_msg = "E-mail inválido."
             elif "cellphone" in raw_error:
                 error_msg = "Número de celular inválido."
                 
             logger.error(f"[{req_id}] Abacate Pay returned failure: {raw_error} -> {error_msg}")
             return jsonify({"error": error_msg}), 400

        data_obj = result.get('data')
        if not data_obj:
            logger.error(f"[{req_id}] No data object in response")
            return jsonify({"error": "Invalid response from payment provider"}), 502

        logger.info(f"[{req_id}] PIX generated successfully")
        
        return jsonify({
            "brCode": data_obj.get('brCode'),
            "brCodeBase64": data_obj.get('brCodeBase64'),
            "pixId": data_obj.get('id')
        })

    except Exception as e:
        logger.exception(f"[{req_id}] Unexpected error in PIX generation: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Vercel needs the 'app' object.
# We also include the main block for local testing
if __name__ == '__main__':
    logger.info("Starting Payment Server on port 5000...")
    app.run(port=5000, debug=True)
