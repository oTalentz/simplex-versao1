import os
import re
import json
import time
import hmac
import base64
import hashlib
import secrets
import sqlite3
import logging
import datetime
import traceback
import csv
import io
import random
import string
from functools import wraps
from flask import Flask, request, jsonify, g
from flask_cors import CORS
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv

load_dotenv()

# Setup Turso/LibSQL if configured
TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL")
if TURSO_DATABASE_URL:
    # Force HTTPS protocol for Vercel/Serverless compatibility
    # WebSockets (wss://) often fail in serverless environments or require specific headers
    TURSO_DATABASE_URL = TURSO_DATABASE_URL.replace("wss://", "https://").replace("libsql://", "https://")

TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN")
USE_TURSO = bool(TURSO_DATABASE_URL and TURSO_AUTH_TOKEN)

libsql_client = None
if USE_TURSO:
    try:
        import libsql_client
    except ImportError:
        print("Warning: TURSO_DATABASE_URL set but libsql-client not installed. Falling back to SQLite.")
        USE_TURSO = False

def _build_log_handlers():
    handlers = [logging.StreamHandler()]
    if os.getenv("VERCEL"):
        return handlers
    try:
        handlers.insert(0, logging.FileHandler("server.log"))
    except Exception:
        pass
    return handlers


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=_build_log_handlers()
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

@app.errorhandler(500)
def internal_error(error):
    # Log the full traceback
    logger.error(f"Internal Server Error: {error}\n{traceback.format_exc()}")
    return jsonify({
        "error": "Internal Server Error",
        "details": str(error),
        "trace": traceback.format_exc()
    }), 500

@app.errorhandler(404)
def not_found_error(error):
    return jsonify({"error": "Not Found"}), 404


@app.route("/api/health", methods=['GET'])
def health_check():
    status = {
        "status": "online",
        "timestamp": now_iso(),
        "environment": "vercel" if os.getenv("VERCEL") else "local",
        "database": "turso" if USE_TURSO else "sqlite"
    }
    
    # Check DB connection
    try:
        conn = get_db_connection()
        conn.execute("SELECT 1").fetchone()
        conn.close()
        status["db_connection"] = "ok"
    except Exception as e:
        status["db_connection"] = "error"
        status["db_error"] = str(e)
        return jsonify(status), 500

    if os.getenv("VERCEL") and not USE_TURSO:
        status["warning"] = "Running on Vercel with ephemeral SQLite database! Data will be lost on restart."

    if os.getenv("VERCEL") and JWT_SECRET == "simplex_dev_secret_change_me":
        status["security_warning"] = "JWT_SECRET is using the default value! Please set a secure random secret."

    return jsonify(status)


@app.route("/api/debug-db", methods=['GET'])
def debug_db():
    try:
        conn = get_db_connection()
        # Try to read tables
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        # Try to count users
        users_count = "Unknown"
        try:
            users = conn.execute("SELECT count(*) as c FROM admin_users").fetchone()
            users_count = users["c"]
        except Exception as e:
            users_count = f"Error: {str(e)}"
        
        conn.close()
        
        return jsonify({
            "status": "online",
            "db_type": "Turso" if USE_TURSO else "SQLite",
            "tables": [dict(row) for row in tables],
            "users_count": users_count,
            "turso_configured": bool(TURSO_DATABASE_URL and TURSO_AUTH_TOKEN)
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e),
            "turso_configured": bool(TURSO_DATABASE_URL and TURSO_AUTH_TOKEN)
        }), 500


try:
    from flask_sock import Sock
    sock = Sock(app)
except Exception:
    class _SockFallback:
        def route(self, *_args, **_kwargs):
            def decorator(fn):
                return fn
            return decorator
    sock = _SockFallback()

DB_NAME = "/tmp/simplex.db" if os.getenv("VERCEL") else "simplex.db"
ABACATE_API_TOKEN = os.getenv("ABACATE_PAY_TOKEN", "")
ABACATE_API_URL = "https://api.abacatepay.com/v1/billing/create"
ABACATE_PIX_URL = "https://api.abacatepay.com/v1/pixQrCode/create"
API_TIMEOUT = int(os.getenv("API_TIMEOUT", "30"))
JWT_SECRET = os.getenv("JWT_SECRET", "simplex_dev_secret_change_me")
JWT_EXP_MINUTES = int(os.getenv("JWT_EXP_MINUTES", "120"))
WEBHOOK_SHARED_SECRET = os.getenv("WEBHOOK_SHARED_SECRET", "")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
HEARTBEAT_WARNING_SECONDS = int(os.getenv("HEARTBEAT_WARNING_SECONDS", "120"))
HEARTBEAT_OFFLINE_SECONDS = int(os.getenv("HEARTBEAT_OFFLINE_SECONDS", "300"))

PRICES = {
    "LORD": 4990,
    "KNIGHT": 7990,
    "GUARDIAN": 9990,
    "CHAMPION": 12990
}


def b64url_encode(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("utf-8")


def b64url_decode(text):
    padding = "=" * ((4 - len(text) % 4) % 4)
    return base64.urlsafe_b64decode((text + padding).encode("utf-8"))


def jwt_encode(payload):
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature = hmac.new(JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
    signature_b64 = b64url_encode(signature)
    return f"{header_b64}.{payload_b64}.{signature_b64}"


def jwt_decode(token):
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Token inválido")
    header_b64, payload_b64, signature_b64 = parts
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    expected = hmac.new(JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
    actual = b64url_decode(signature_b64)
    if not hmac.compare_digest(expected, actual):
        raise ValueError("Assinatura inválida")
    payload = json.loads(b64url_decode(payload_b64))
    now = int(time.time())
    if int(payload.get("exp", 0)) < now:
        raise ValueError("Token expirado")
    return payload


def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 130000)
    return f"{salt}${hashed.hex()}"


def verify_password(password, stored):
    if "$" not in stored:
        return False
    salt, digest = stored.split("$", 1)
    return hmac.compare_digest(hash_password(password, salt), f"{salt}${digest}")


class TursoCursorWrapper:
    def __init__(self, result_set):
        self.result_set = result_set
        self.current_index = 0
        # Convert columns to list of names if they are objects
        self.columns = list(result_set.columns) if result_set.columns else []

    def fetchone(self):
        if self.current_index < len(self.result_set.rows):
            row = self.result_set.rows[self.current_index]
            self.current_index += 1
            # Return a dict-like object (sqlite3.Row emulation)
            return dict(zip(self.columns, row))
        return None

    def fetchall(self):
        return [dict(zip(self.columns, row)) for row in self.result_set.rows]

    def close(self):
        pass


class TursoConnectionWrapper:
    def __init__(self, url, auth_token):
        # Create client inside a try block to catch connection errors immediately
        try:
            self.client = libsql_client.create_client_sync(url=url, auth_token=auth_token)
        except Exception as e:
            logger.error(f"Failed to create Turso client: {e}")
            raise e
        self.row_factory = None  # Emulator placeholder

    def execute(self, sql, params=()):
        try:
            # Ensure params is a tuple or list
            if params is None:
                params = ()
            elif not isinstance(params, (list, tuple)):
                params = (params,)
                
            rs = self.client.execute(sql, params)
            return TursoCursorWrapper(rs)
        except Exception as e:
            logger.error(f"Turso execute error: {e} | SQL: {sql} | Params: {params}")
            raise e

    def commit(self):
        pass

    def close(self):
        self.client.close()


def get_db_connection():
    if USE_TURSO and libsql_client:
        return TursoConnectionWrapper(TURSO_DATABASE_URL, TURSO_AUTH_TOKEN)
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY,
            customer_name TEXT,
            customer_email TEXT,
            customer_cpf TEXT,
            product TEXT,
            amount INTEGER,
            status TEXT,
            delivery_status TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor TEXT NOT NULL,
            action TEXT NOT NULL,
            status TEXT NOT NULL,
            ip TEXT,
            metadata TEXT,
            created_at TIMESTAMP NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS connector_cache (
            cache_key TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            updated_at TIMESTAMP NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pairing_codes (
            code TEXT PRIMARY KEY,
            agent_name TEXT,
            status TEXT DEFAULT 'PENDING',
            token TEXT,
            revoked INTEGER DEFAULT 0,
            created_at TIMESTAMP
        )
    """)
    try:
        conn.execute("ALTER TABLE pairing_codes ADD COLUMN revoked INTEGER DEFAULT 0")
    except Exception:
        pass

    conn.execute("""
        CREATE TABLE IF NOT EXISTS coupons (
            code TEXT PRIMARY KEY,
            discount_type TEXT DEFAULT 'PERCENT', -- 'PERCENT' or 'FIXED'
            discount_value INTEGER DEFAULT 0, -- percent or fixed amount in cents
            max_uses INTEGER DEFAULT -1,
            used_count INTEGER DEFAULT 0,
            expires_at TIMESTAMP,
            min_cart_value INTEGER DEFAULT 0,
            status TEXT DEFAULT 'ACTIVE', -- 'ACTIVE' or 'INACTIVE'
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)

    # Migration for coupons table if it has old schema
    try:
        cur = conn.execute("PRAGMA table_info(coupons)")
        columns = [row["name"] for row in cur.fetchall()]
        if "discount_percent" in columns and "discount_type" not in columns:
            # Old schema detected, migrate
            logger.info("Migrating coupons table to new schema...")
            # Rename old table
            conn.execute("ALTER TABLE coupons RENAME TO coupons_old")
            # Create new table
            conn.execute("""
                CREATE TABLE coupons (
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
            # Migrate data
            old_coupons = conn.execute("SELECT * FROM coupons_old").fetchall()
            for old in old_coupons:
                d_type = 'PERCENT'
                d_val = old['discount_percent']
                if old['discount_amount'] > 0:
                    d_type = 'FIXED'
                    d_val = old['discount_amount']
                
                conn.execute("""
                    INSERT INTO coupons (code, discount_type, discount_value, max_uses, used_count, expires_at, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (old['code'], d_type, d_val, old['max_uses'], old['used_count'], old['expires_at'], now_iso(), now_iso()))
            
            conn.execute("DROP TABLE coupons_old")
    except Exception as e:
        logger.error(f"Migration failed: {e}")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS coupon_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            coupon_code TEXT,
            customer_email TEXT,
            order_id TEXT,
            used_at TIMESTAMP,
            FOREIGN KEY (coupon_code) REFERENCES coupons(code)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS coupon_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            coupon_code TEXT,
            admin_user TEXT,
            action TEXT,
            details TEXT,
            timestamp TIMESTAMP
        )
    """)
    try:
        conn.execute("ALTER TABLE orders ADD COLUMN coupon_code TEXT")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE orders ADD COLUMN discount_amount INTEGER DEFAULT 0")
    except Exception:
        pass

    try:
        conn.execute("ALTER TABLE orders ADD COLUMN delivery_status TEXT DEFAULT 'PENDING'")
    except Exception:
        pass

    admin = conn.execute("SELECT id FROM admin_users WHERE username = ?", (ADMIN_USERNAME,)).fetchone()
    if not admin:
        conn.execute(
            "INSERT INTO admin_users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
            (ADMIN_USERNAME, hash_password(ADMIN_PASSWORD), "superadmin", now_iso())
        )
    conn.commit()
    conn.close()


try:
    init_db()
except Exception as e:
    logger.error(f"Failed to initialize database: {e}")
    # Continue running app, but database operations will fail
    pass


def audit(actor, action, status, metadata=None):
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO audit_logs (actor, action, status, ip, metadata, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (
            actor,
            action,
            status,
            request.headers.get("X-Forwarded-For", request.remote_addr),
            json.dumps(metadata or {}, ensure_ascii=False),
            now_iso()
        )
    )
    conn.commit()
    conn.close()


def log_coupon_change(code, action, details, admin_user):
    try:
        conn = get_db_connection()
        conn.execute("""
            INSERT INTO coupon_logs (coupon_code, admin_user, action, details, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (code, admin_user, action, json.dumps(details, ensure_ascii=False), now_iso()))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to log coupon change: {e}")


def get_requests_session():
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=0.8, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET", "POST"])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def require_json():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, (jsonify({"error": "JSON inválido"}), 400)
    return data, None


def validate_customer_data(data):
    required = ["nickname", "email", "product"]
    missing = [field for field in required if not data.get(field)]
    if missing:
        return False, f"Campos obrigatórios ausentes: {', '.join(missing)}"

    nickname = str(data.get("nickname", "")).strip()
    if not re.fullmatch(r"[a-zA-Z0-9_]{3,16}", nickname):
        return False, "Nickname inválido"

    email = str(data.get("email", "")).strip()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return False, "Email inválido"

    # CPF check removed as requested

    product_name = str(data.get("product", "")).replace("KIT", "").strip().upper()
    if product_name not in PRICES:
        return False, f"Produto inválido: {product_name}"

    return True, None


def sanitize_phone(phone):
    clean = "".join(filter(str.isdigit, str(phone or "")))
    if len(clean) in (10, 11):
        return f"55{clean}"
    if len(clean) >= 12:
        return clean
    return "5511999999999"


def require_auth(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "Token ausente"}), 401
        token = auth.split(" ", 1)[1].strip()
        try:
            payload = jwt_decode(token)
            g.user = payload
        except Exception as exc:
            return jsonify({"error": str(exc)}), 401
        return fn(*args, **kwargs)
    return wrapped


def deliver_vip_rcon(nickname, product):
    bridge_url = os.getenv("VIP_DELIVERY_BRIDGE_URL", "").strip()
    bridge_token = os.getenv("VIP_DELIVERY_BRIDGE_TOKEN", "").strip()
    if bridge_url:
        session = get_requests_session()
        headers = {"Content-Type": "application/json"}
        if bridge_token:
            headers["X-Bridge-Token"] = bridge_token
        payload = {"nickname": nickname, "product": product}
        try:
            response = session.post(bridge_url, json=payload, headers=headers, timeout=min(API_TIMEOUT, 15))
            return response.status_code in (200, 201, 202)
        except Exception:
            return False
    return False


def _parse_iso(value):
    if isinstance(value, datetime.datetime):
        return value
    if not value:
        return None
    try:
        return datetime.datetime.fromisoformat(str(value))
    except Exception:
        return None


def _get_latest_connector_heartbeat(conn):
    rows = conn.execute(
        "SELECT payload, updated_at FROM connector_cache ORDER BY updated_at DESC LIMIT 200"
    ).fetchall()
    for row in rows:
        try:
            payload = json.loads(row["payload"])
        except Exception:
            continue
        if str(payload.get("type", "")).strip().lower() == "heartbeat":
            return _parse_iso(row["updated_at"]), payload.get("payload", {})
    return None, {}


def _mc_online_state(heartbeat_at):
    if not heartbeat_at:
        return "offline"
    if heartbeat_at.tzinfo is None:
        heartbeat_at = heartbeat_at.replace(tzinfo=datetime.timezone.utc)
    now = datetime.datetime.now(datetime.timezone.utc)
    age = (now - heartbeat_at).total_seconds()
    if age <= HEARTBEAT_WARNING_SECONDS:
        return "online"
    if age <= HEARTBEAT_OFFLINE_SECONDS:
        return "warning"
    return "offline"


@app.route("/api/")
def home():
    return jsonify({"status": "ok", "service": "Simplex Payment API"})


@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    try:
        data, err = require_json()
        if err:
            return err

        username = str(data.get("username", "")).strip()
        password = str(data.get("password", ""))

        if not username or not password:
            return jsonify({"error": "Credenciais inválidas"}), 400

        conn = get_db_connection()
        user = conn.execute("SELECT * FROM admin_users WHERE username = ?", (username,)).fetchone()
        conn.close()

        if not user or not verify_password(password, user["password_hash"]):
            audit(username or "unknown", "auth_login", "failed")
            return jsonify({"error": "Usuário ou senha inválidos"}), 401

        now = int(time.time())
        payload = {
            "sub": username,
            "role": user["role"],
            "iat": now,
            "exp": now + JWT_EXP_MINUTES * 60
        }
        token = jwt_encode(payload)
        audit(username, "auth_login", "success")

        return jsonify({
            "token": token,
            "expires_in": JWT_EXP_MINUTES * 60,
            "role": user["role"]
        })
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({"error": "Internal Server Error", "details": traceback.format_exc()}), 500


@app.route("/api/auth/me", methods=["GET"])
@require_auth
def auth_me():
    return jsonify({"username": g.user.get("sub"), "role": g.user.get("role")})


def _validate_coupon_logic(code, original_amount, customer_email=None):
    if not code:
        return True, "", 0, 0

    code = code.strip().upper()
    conn = get_db_connection()
    coupon = conn.execute("SELECT * FROM coupons WHERE code = ?", (code,)).fetchone()
    
    if not coupon:
        conn.close()
        return False, "Cupom não encontrado", 0, 0

    # Check status
    # Convert Row to dict to use .get() safely
    coupon_data = dict(coupon)
    if coupon_data.get("status", "ACTIVE") != "ACTIVE":
        conn.close()
        return False, "Cupom inativo", 0, 0

    # Check expiration
    if coupon_data.get("expires_at"):
        try:
            expires = datetime.datetime.fromisoformat(coupon_data["expires_at"])
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=datetime.timezone.utc)
            if datetime.datetime.now(datetime.timezone.utc) > expires:
                conn.close()
                return False, "Cupom expirado", 0, 0
        except Exception:
            pass

    # Check usage limit (overall)
    if coupon["max_uses"] != -1 and coupon["used_count"] >= coupon["max_uses"]:
        conn.close()
        return False, "Limite de uso global atingido", 0, 0

    # Check minimum cart value
    min_val = coupon_data.get("min_cart_value", 0)
    if original_amount < min_val:
        conn.close()
        return False, f"Valor mínimo para este cupom é R$ {min_val/100:.2f}", 0, 0

    # Check per-customer limit (if email provided)
    if customer_email:
        usage = conn.execute(
            "SELECT count(*) as count FROM coupon_usage WHERE coupon_code = ? AND customer_email = ?",
            (code, customer_email)
        ).fetchone()
        if usage and usage["count"] >= 1: # Assuming limit 1 per customer for now
            conn.close()
            return False, "Você já utilizou este cupom", 0, 0

    conn.close()

    discount_amount = 0
    discount_type = coupon_data.get("discount_type", "PERCENT")
    discount_value = coupon_data.get("discount_value", 0)

    if discount_type == "PERCENT":
        discount_amount = int(original_amount * (discount_value / 100))
    else:
        discount_amount = discount_value

    # Cap discount at original amount
    if discount_amount > original_amount:
        discount_amount = original_amount

    percent = discount_value if discount_type == "PERCENT" else 0
    return True, "Cupom aplicado com sucesso", percent, discount_amount


@app.route('/validate-coupon', methods=['POST'])
@app.route('/api/validate-coupon', methods=['POST'])
def validate_coupon_endpoint():
    data, err = require_json()
    if err:
        return err
    
    code = data.get("code", "")
    product_name = str(data.get("product", "")).replace("KIT", "").strip().upper()
    
    if product_name not in PRICES:
        return jsonify({"error": "Produto inválido"}), 400

    original_amount = PRICES[product_name]
    # For validation endpoint, we might not have email yet, or it's optional.
    # If the user wants to check if *they* can use it, they should send email.
    email = data.get("email", "")
    is_valid, msg, percent, discount = _validate_coupon_logic(code, original_amount, email)
    
    if not is_valid:
        return jsonify({"valid": False, "message": msg}), 200

    final_price = original_amount - discount
    return jsonify({
        "valid": True,
        "message": msg,
        "original_price": original_amount,
        "discount_amount": discount,
        "final_price": final_price,
        "percent": percent
    })


def _record_coupon_usage(conn, coupon_code, email, order_id):
    if not coupon_code:
        return
    
    try:
        conn.execute("UPDATE coupons SET used_count = used_count + 1 WHERE code = ?", (coupon_code,))
        
        if email:
            conn.execute(
                "INSERT INTO coupon_usage (coupon_code, customer_email, order_id, used_at) VALUES (?, ?, ?, ?)",
                (coupon_code, email, order_id, now_iso())
            )
    except Exception as e:
        logger.error(f"Failed to record coupon usage for {coupon_code}: {e}")
        # Do not raise exception to avoid blocking the order

@app.route('/payment/create', methods=['POST'])
@app.route('/api/payment/create', methods=['POST'])
def create_payment():
    req_id = int(time.time() * 1000)
    data, err = require_json()
    if err:
        return err
    is_valid, error_msg = validate_customer_data(data)
    if not is_valid:
        audit("public", "create_payment", "failed", {"error": error_msg, "req_id": req_id})
        return jsonify({"error": error_msg}), 400
    nickname = data.get("nickname")
    email = data.get("email")
    cpf_clean = "".join(filter(str.isdigit, str(data.get("cpf"))))
    product_name = str(data.get("product", "")).replace("KIT", "").strip().upper()
    amount = PRICES[product_name]

    coupon_code = data.get("coupon", "")
    is_valid, msg, percent, discount = _validate_coupon_logic(coupon_code, amount, email)
    if coupon_code and not is_valid:
        return jsonify({"error": msg}), 400

    final_amount = amount - discount

    payload = {
        "frequency": "ONE_TIME",
        "methods": ["PIX"],
        "products": [{"externalId": product_name, "name": f"VIP {product_name}", "quantity": 1, "price": final_amount, "description": f"VIP {product_name} para {nickname}"}],
        "returnUrl": os.getenv("RETURN_URL", "http://localhost:5500/success"),
        "completionUrl": os.getenv("COMPLETION_URL", "http://localhost:5500/success"),
        "customer": {"name": nickname, "email": email, "taxId": "", "cellphone": sanitize_phone(data.get("cellphone"))}
    }
    session = get_requests_session()
    headers = {"Authorization": f"Bearer {ABACATE_API_TOKEN}", "Content-Type": "application/json"}
    try:
        response = session.post(ABACATE_API_URL, json=payload, headers=headers, timeout=API_TIMEOUT)
        result = response.json()
        if response.status_code != 200:
            audit("public", "create_payment", "failed", {"status": response.status_code, "req_id": req_id})
            return jsonify({"error": "Payment Gateway Error", "details": result}), response.status_code
        bill_id = result.get("data", {}).get("id")
        url = result.get("data", {}).get("url")
        if not bill_id or not url:
            audit("public", "create_payment", "failed", {"error": "missing_payment_fields", "req_id": req_id})
            return jsonify({"error": "Resposta inválida do gateway"}), 502
        conn = get_db_connection()
        conn.execute(
            "INSERT OR IGNORE INTO orders (id, customer_name, customer_email, customer_cpf, product, amount, status, delivery_status, created_at, updated_at, coupon_code, discount_amount) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (bill_id, nickname, email, "", product_name, final_amount, "PENDING", "PENDING", now_iso(), now_iso(), coupon_code, discount)
        )
        if discount > 0:
            _record_coupon_usage(conn, coupon_code, email, bill_id)
        conn.commit()
        conn.close()
        audit("public", "create_payment", "success", {"bill_id": bill_id, "req_id": req_id})
        return jsonify({"url": url, "bill_id": bill_id})
    except requests.exceptions.Timeout:
        audit("public", "create_payment", "failed", {"error": "timeout", "req_id": req_id})
        return jsonify({"error": "Payment Gateway Timeout"}), 504
    except requests.exceptions.ConnectionError:
        audit("public", "create_payment", "failed", {"error": "connection_error", "req_id": req_id})
        return jsonify({"error": "Connection Error"}), 503
    except Exception as exc:
        logger.exception("create_payment error")
        audit("public", "create_payment", "failed", {"error": str(exc), "req_id": req_id})
        return jsonify({"error": "Internal Server Error"}), 500


@app.route('/create-pix-payment', methods=['POST'])
@app.route('/api/create-pix-payment', methods=['POST'])
@app.route('/payment/create-pix', methods=['POST'])
@app.route('/api/payment/create-pix', methods=['POST'])
def create_pix_payment():
    data, err = require_json()
    if err:
        return err
    is_valid, error_msg = validate_customer_data(data)
    if not is_valid:
        return jsonify({"error": error_msg}), 400
    nickname = data.get("nickname")
    email = data.get("email")
    cpf_clean = "".join(filter(str.isdigit, str(data.get("cpf"))))
    product_name = str(data.get("product", "")).replace("KIT", "").strip().upper()
    amount = PRICES[product_name]

    coupon_code = data.get("coupon", "")
    is_valid_coupon, msg, percent, discount = _validate_coupon_logic(coupon_code, amount, email)
    if coupon_code and not is_valid_coupon:
        return jsonify({"error": msg}), 400

    final_amount = amount - discount

    # Handle 100% discount (Free Order)
    if final_amount <= 0:
        try:
            free_id = f"free_{int(time.time() * 1000)}"
            conn = get_db_connection()
            conn.execute(
                "INSERT INTO orders (id, customer_name, customer_email, customer_cpf, product, amount, status, delivery_status, created_at, updated_at, coupon_code, discount_amount) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (free_id, nickname, email, cpf_clean, product_name, 0, "PAID", "PENDING", now_iso(), now_iso(), coupon_code, discount)
            )
            if discount > 0:
                _record_coupon_usage(conn, coupon_code, email, free_id)
            
            # Trigger delivery immediately
            delivered = deliver_vip_rcon(nickname, product_name)
            delivery_status = "DELIVERED" if delivered else "PENDING"
            conn.execute("UPDATE orders SET delivery_status = ?, updated_at = ? WHERE id = ?", (delivery_status, now_iso(), free_id))
            
            conn.commit()
            conn.close()
            
            return jsonify({
                "success": True, 
                "free": True, 
                "message": "Cupom de 100% aplicado! VIP ativado com sucesso." if delivered else "Cupom de 100% aplicado! Ativação em processamento."
            })
        except Exception as e:
            logger.exception("Error processing free order")
            return jsonify({"error": "Erro ao processar pedido gratuito", "details": str(e)}), 500

    payload = {
        "amount": final_amount,
        "description": f"VIP {product_name} - {nickname}",
        "customer": {"name": nickname, "email": email, "taxId": cpf_clean, "cellphone": sanitize_phone(data.get("cellphone"))}
    }
    headers = {"Authorization": f"Bearer {ABACATE_API_TOKEN}", "Content-Type": "application/json"}
    session = get_requests_session()
    response = session.post(ABACATE_PIX_URL, json=payload, headers=headers, timeout=API_TIMEOUT)
    result = response.json()
    if response.status_code != 200:
        return jsonify({"error": "Payment Gateway Error", "details": result}), response.status_code
    data_obj = result.get("data", {})
    pix_id = data_obj.get("id")
    conn = get_db_connection()
    conn.execute(
        "INSERT OR IGNORE INTO orders (id, customer_name, customer_email, customer_cpf, product, amount, status, delivery_status, created_at, updated_at, coupon_code, discount_amount) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (pix_id, nickname, email, cpf_clean, product_name, final_amount, "PENDING", "PENDING", now_iso(), now_iso(), coupon_code, discount)
    )
    if discount > 0:
        _record_coupon_usage(conn, coupon_code, email, pix_id)
    conn.commit()
    conn.close()
    return jsonify({"brCode": data_obj.get("brCode"), "brCodeBase64": data_obj.get("brCodeBase64"), "pixId": pix_id})


@app.route('/api/webhooks/abacate', methods=['POST'])
def abacate_webhook():
    if WEBHOOK_SHARED_SECRET:
        provided = request.headers.get("X-Webhook-Token", "")
        if not hmac.compare_digest(provided, WEBHOOK_SHARED_SECRET):
            audit("webhook", "abacate_webhook", "failed", {"reason": "invalid_signature"})
            return jsonify({"error": "Assinatura inválida"}), 401
    data, err = require_json()
    if err:
        return err
    bill_id = data.get("data", {}).get("id")
    status_raw = (data.get("data", {}).get("status") or "").upper()
    event_type = (data.get("event") or "").upper()
    if not bill_id:
        return jsonify({"error": "No bill ID found"}), 400
    conn = get_db_connection()
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (bill_id,)).fetchone()
    if not order:
        conn.close()
        audit("webhook", "abacate_webhook", "ignored", {"bill_id": bill_id, "reason": "missing_order"})
        return jsonify({"message": "Order not found, ignored"}), 200
    new_status = "PENDING"
    if status_raw == "PAID" or event_type == "BILLING.PAID":
        new_status = "PAID"
    elif status_raw in ("FAILED", "CANCELED"):
        new_status = "FAILED"
    if order["status"] == new_status and order["delivery_status"] == "DELIVERED":
        conn.close()
        audit("webhook", "abacate_webhook", "deduplicated", {"bill_id": bill_id})
        return jsonify({"success": True, "deduplicated": True}), 200
    conn.execute("UPDATE orders SET status = ?, updated_at = ? WHERE id = ?", (new_status, now_iso(), bill_id))
    if new_status == "PAID" and order["delivery_status"] != "DELIVERED":
        delivered = deliver_vip_rcon(order["customer_name"], order["product"])
        delivery_status = "DELIVERED" if delivered else "PENDING"
        conn.execute("UPDATE orders SET delivery_status = ?, updated_at = ? WHERE id = ?", (delivery_status, now_iso(), bill_id))
    conn.commit()
    conn.close()
    audit("webhook", "abacate_webhook", "success", {"bill_id": bill_id, "status": new_status})
    return jsonify({"success": True}), 200


def _stats_payload(days):
    cutoff = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)).replace(microsecond=0).isoformat()
    conn = get_db_connection()
    stats = conn.execute("""
        SELECT
            SUM(CASE WHEN status = 'PAID' THEN amount ELSE 0 END) as total_revenue,
            COUNT(CASE WHEN status = 'PAID' THEN 1 END) as vips_paid,
            COUNT(CASE WHEN delivery_status IN ('PENDING', 'ROLLBACK_PENDING') AND status = 'PAID' THEN 1 END) as vips_pending_delivery
        FROM orders
        WHERE created_at >= ?
    """, (cutoff,)).fetchone()
    recent = conn.execute("SELECT id, customer_name, product, amount, status, delivery_status, created_at FROM orders ORDER BY created_at DESC LIMIT 20").fetchall()
    conn.close()
    total_revenue = stats["total_revenue"] or 0
    return {
        "total_revenue": total_revenue,
        "net_profit": round(total_revenue * 0.95, 2),
        "vips_paid": stats["vips_paid"] or 0,
        "vips_pending_delivery": stats["vips_pending_delivery"] or 0,
        "recent_orders": [dict(row) for row in recent]
    }


def _status_payload():
    payload = {
        "api_status": "online",
        "db_status": "online",
        "mc_status": "offline",
        "payment_status": "online" if ABACATE_API_TOKEN else "warning",
        "mc_server_name": None,
        "mc_players_online": 0,
        "mc_last_seen": None
    }
    try:
        conn = get_db_connection()
        conn.execute("SELECT 1").fetchone()
        heartbeat_at, heartbeat_data = _get_latest_connector_heartbeat(conn)
        
        status = _mc_online_state(heartbeat_at)
        payload["mc_status"] = status
        
        if status != "offline" and heartbeat_data:
            # Check for override in settings
            settings_name = conn.execute("SELECT value FROM settings WHERE key = 'server_name'").fetchone()
            payload["mc_server_name"] = settings_name["value"] if settings_name else heartbeat_data.get("agent", "Unknown")
            payload["mc_players_online"] = heartbeat_data.get("online", 0)
            payload["mc_last_seen"] = heartbeat_at.isoformat() if heartbeat_at else None
            
        conn.close()
            
    except Exception:
        payload["db_status"] = "offline"
        payload["mc_status"] = "offline"
    return payload


@app.route('/api/admin/stats', methods=['GET'])
@require_auth
def admin_stats():
    days = int(request.args.get("days", "30"))
    audit(g.user.get("sub"), "admin_stats", "success", {"days": days})
    return jsonify(_stats_payload(days))


@app.route('/api/admin/status', methods=['GET'])
@require_auth
def admin_status():
    audit(g.user.get("sub"), "admin_status", "success")
    return jsonify(_status_payload())


@app.route('/api/admin/audit', methods=['GET'])
@require_auth
def admin_audit():
    limit = min(int(request.args.get("limit", "100")), 300)
    conn = get_db_connection()
    rows = conn.execute("SELECT actor, action, status, ip, metadata, created_at FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return jsonify({"logs": [dict(row) for row in rows]})


@app.route('/api/connector/events', methods=['POST'])
@require_auth
def connector_events():
    data, err = require_json()
    if err:
        return err
    event_type = str(data.get("type", "")).strip()
    payload = data.get("payload", {})
    if not event_type:
        return jsonify({"error": "type é obrigatório"}), 400
    
    conn = get_db_connection()
    
    # Check if token is revoked
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        row = conn.execute("SELECT revoked FROM pairing_codes WHERE token = ?", (token,)).fetchone()
        if row and row["revoked"]:
            conn.close()
            return jsonify({"error": "Token revoked"}), 403

    conn.execute(
        "INSERT OR REPLACE INTO connector_cache (cache_key, payload, updated_at) VALUES (?, ?, ?)",
        (f"{g.user.get('sub')}:{int(time.time() * 1000)}", json.dumps({"type": event_type, "payload": payload}), now_iso())
    )
    conn.commit()
    conn.close()
    audit(g.user.get("sub"), "connector_events", "success", {"type": event_type})
    return jsonify({"success": True})


@app.route('/api/connector/setup/init', methods=['POST'])
def connector_setup_init():
    data, err = require_json()
    if err:
        return err
    code = str(data.get("code", "")).strip().upper()
    agent = str(data.get("agent", "")).strip()
    if not code or not agent:
        return jsonify({"error": "Missing code or agent"}), 400

    conn = get_db_connection()
    existing = conn.execute("SELECT status, token FROM pairing_codes WHERE code = ?", (code,)).fetchone()
    
    if existing:
        if existing["status"] == "CLAIMED":
            conn.close()
            return jsonify({"status": "CLAIMED", "token": existing["token"]})
        conn.execute("UPDATE pairing_codes SET agent_name = ?, created_at = ? WHERE code = ?", (agent, now_iso(), code))
    else:
        conn.execute("INSERT INTO pairing_codes (code, agent_name, status, created_at) VALUES (?, ?, 'PENDING', ?)", (code, agent, now_iso()))
    
    conn.commit()
    conn.close()
    return jsonify({"status": "PENDING"})


@app.route('/api/connector/setup/poll', methods=['GET'])
def connector_setup_poll():
    code = request.args.get("code", "").strip().upper()
    if not code:
        return jsonify({"error": "Missing code"}), 400

    conn = get_db_connection()
    row = conn.execute("SELECT status, token, created_at FROM pairing_codes WHERE code = ?", (code,)).fetchone()
    conn.close()

    if not row:
        return jsonify({"status": "NOT_FOUND"}), 404

    if row["status"] == "CLAIMED":
        return jsonify({"status": "CLAIMED", "token": row["token"]})

    # Check expiration (10 minutes)
    try:
        created_at = datetime.datetime.fromisoformat(row["created_at"])
        # Ensure timezone awareness compatibility
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=datetime.timezone.utc)
        
        now = datetime.datetime.now(datetime.timezone.utc)
        if (now - created_at).total_seconds() > 600: # 10 minutes
            return jsonify({"status": "EXPIRED"}), 200
    except Exception:
        pass # If date parsing fails, assume valid

    return jsonify({"status": "PENDING"})


@app.route('/api/admin/connector/claim', methods=['POST'])
@require_auth
def admin_claim_connector():
    if g.user.get("role") != "superadmin":
        return jsonify({"error": "Forbidden"}), 403

    data, err = require_json()
    if err:
        return err
    code = str(data.get("code", "")).strip().upper()
    
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM pairing_codes WHERE code = ?", (code,)).fetchone()
    
    if not row:
        conn.close()
        return jsonify({"error": "Código não encontrado"}), 404

    if row["status"] == "CLAIMED":
        conn.close()
        return jsonify({"error": "Código já resgatado"}), 400

    agent_name = row["agent_name"]
    now = int(time.time())
    # Token valido por 10 anos para o conector
    payload = {"sub": f"connector_{agent_name}_{code}", "role": "connector", "iat": now, "exp": now + 315360000}
    token = jwt_encode(payload)

    conn.execute("UPDATE pairing_codes SET status = 'CLAIMED', token = ? WHERE code = ?", (token, code))
    conn.commit()
    conn.close()

    audit(g.user.get("sub"), "claim_connector", "success", {"code": code, "agent": agent_name})
    return jsonify({"success": True, "agent": agent_name, "token": token})


@app.route('/api/admin/connector/disconnect', methods=['POST'])
@require_auth
def admin_connector_disconnect():
    # Revoke active token logic
    # Find the most recent active connector from cache
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT cache_key, payload FROM connector_cache ORDER BY updated_at DESC LIMIT 1"
    ).fetchall()
    
    revoked_count = 0
    if rows:
        try:
            # cache_key format: sub:timestamp
            cache_key = rows[0]["cache_key"]
            sub = cache_key.split(":")[0]
            
            # Find pairing code with this sub (token sub matches)
            # Actually, sub is in the token. We need to find the token that produces this sub?
            # Or just clear the cache and rely on token revocation if we had it.
            # But we added 'revoked' column to pairing_codes.
            # We need to find which code corresponds to this sub.
            # sub format: connector_{agent}_{code}
            # We can extract code from sub.
            parts = sub.split("_")
            if len(parts) >= 3:
                code = parts[-1]
                conn.execute("UPDATE pairing_codes SET revoked = 1 WHERE code = ?", (code,))
                revoked_count = conn.total_changes
        except Exception as e:
            logger.error(f"Error revoking token: {e}")

    # Clear cache
    conn.execute("DELETE FROM connector_cache")
    # Also clear server_name setting
    conn.execute("DELETE FROM settings WHERE key = 'server_name'")
    
    conn.commit()
    conn.close()
    
    audit(g.user.get("sub"), "connector_disconnect", "success", {"revoked": revoked_count})
    return jsonify({"success": True})


@app.route('/admin/settings', methods=['GET', 'POST'])
@require_auth
def admin_settings():
    conn = get_db_connection()
    if request.method == 'POST':
        data, err = require_json()
        if err:
            return err
        key = str(data.get("key", "")).strip()
        value = str(data.get("value", "")).strip()
        if not key:
            return jsonify({"error": "Key is required"}), 400
        
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        conn.commit()
        conn.close()
        audit(g.user.get("sub"), "update_setting", "success", {"key": key, "value": value})
        return jsonify({"success": True})
    else:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        conn.close()
        return jsonify({row["key"]: row["value"] for row in rows})


@app.route('/connector/cache', methods=['GET'])
@require_auth
def connector_cache():
    limit = min(int(request.args.get("limit", "100")), 300)
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT cache_key, payload, updated_at FROM connector_cache ORDER BY updated_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return jsonify({"items": [dict(row) for row in rows]})


@app.route('/connector/deliveries', methods=['GET'])
@require_auth
def connector_deliveries():
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT id, customer_name, product FROM orders WHERE status = 'PAID' AND delivery_status = 'PENDING' LIMIT 50"
    ).fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])


@app.route('/connector/deliveries/confirm', methods=['POST'])
@require_auth
def connector_confirm_delivery():
    data, err = require_json()
    if err:
        return err
    order_id = data.get("id")
    if not order_id:
        return jsonify({"error": "id é obrigatório"}), 400
    conn = get_db_connection()
    conn.execute(
        "UPDATE orders SET delivery_status = 'DELIVERED', updated_at = ? WHERE id = ?",
        (now_iso(), order_id)
    )
    conn.commit()
    conn.close()
    audit(g.user.get("sub"), "connector_confirm_delivery", "success", {"order_id": order_id})
    return jsonify({"success": True})


@sock.route('/ws')
def connector_ws(ws):
    auth_header = ws.environ.get("HTTP_AUTHORIZATION", "")
    if not auth_header.startswith("Bearer "):
        ws.send(json.dumps({"error": "Token ausente"}))
        ws.close()
        return
    token = auth_header.split(" ", 1)[1].strip()
    try:
        payload = jwt_decode(token)
    except Exception as exc:
        ws.send(json.dumps({"error": str(exc)}))
        ws.close()
        return
    while True:
        message = ws.receive()
        if message is None:
            break
        try:
            event = json.loads(message)
            event_type = str(event.get("type", "")).strip()
            if not event_type:
                ws.send(json.dumps({"error": "type é obrigatório"}))
                continue
            conn = get_db_connection()
            conn.execute(
                "INSERT OR REPLACE INTO connector_cache (cache_key, payload, updated_at) VALUES (?, ?, ?)",
                (f"{payload.get('sub')}:{int(time.time() * 1000)}", json.dumps(event), now_iso())
            )
            conn.commit()
            conn.close()
            ws.send(json.dumps({"success": True, "type": event_type}))
        except Exception as exc:
            ws.send(json.dumps({"error": str(exc)}))


@app.route("/swagger.json", methods=["GET"])
def swagger_json():
    schema_path = os.path.join(os.path.dirname(__file__), "swagger.json")
    if not os.path.exists(schema_path):
        return jsonify({"error": "Swagger não encontrado"}), 404
    with open(schema_path, "r", encoding="utf-8") as file:
        return jsonify(json.load(file))


@app.route('/admin/coupons', methods=['GET'])
@app.route('/api/admin/coupons', methods=['GET'])
@require_auth
def admin_get_coupons():
    conn = get_db_connection()
    coupons = conn.execute("SELECT * FROM coupons ORDER BY created_at DESC").fetchall()
    conn.close()
    return jsonify([dict(row) for row in coupons])

@app.route('/admin/coupons', methods=['POST'])
@app.route('/api/admin/coupons', methods=['POST'])
@require_auth
def admin_create_coupon():
    data, err = require_json()
    if err: return err
    
    code = str(data.get("code", "")).strip().upper()
    if not code:
        # Generate random code if not provided
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    
    conn = get_db_connection()
    exists = conn.execute("SELECT 1 FROM coupons WHERE code = ?", (code,)).fetchone()
    if exists:
        conn.close()
        return jsonify({"error": "Código já existe"}), 400
        
    try:
        conn.execute("""
            INSERT INTO coupons (
                code, discount_type, discount_value, max_uses, used_count, expires_at, min_cart_value, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?, ?)
        """, (
            code,
            data.get("discount_type", "PERCENT"),
            int(data.get("discount_value", 0)),
            int(data.get("max_uses", -1)),
            data.get("expires_at"), # Expects ISO format or None
            int(data.get("min_cart_value", 0)),
            data.get("status", "ACTIVE"),
            now_iso(),
            now_iso()
        ))
        conn.commit()
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 500
        
    conn.close()
    audit(g.user.get("sub"), "create_coupon", "success", {"code": code})
    log_coupon_change(code, "CREATE", data, g.user.get("sub"))
    return jsonify({"success": True, "code": code})

@app.route('/admin/coupons/<code>', methods=['PUT'])
@app.route('/api/admin/coupons/<code>', methods=['PUT'])
@require_auth
def admin_update_coupon(code):
    data, err = require_json()
    if err: return err
    
    code = code.upper()
    conn = get_db_connection()
    
    old_coupon = conn.execute("SELECT * FROM coupons WHERE code = ?", (code,)).fetchone()
    if not old_coupon:
        conn.close()
        return jsonify({"error": "Cupom não encontrado"}), 404
    old_data = dict(old_coupon)

    try:
        conn.execute("""
            UPDATE coupons SET
                discount_type = ?,
                discount_value = ?,
                max_uses = ?,
                expires_at = ?,
                min_cart_value = ?,
                status = ?,
                updated_at = ?
            WHERE code = ?
        """, (
            data.get("discount_type", "PERCENT"),
            int(data.get("discount_value", 0)),
            int(data.get("max_uses", -1)),
            data.get("expires_at"),
            int(data.get("min_cart_value", 0)),
            data.get("status", "ACTIVE"),
            now_iso(),
            code
        ))
        conn.commit()
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 500
        
    conn.close()
    audit(g.user.get("sub"), "update_coupon", "success", {"code": code})
    log_coupon_change(code, "UPDATE", {"before": old_data, "after": data}, g.user.get("sub"))
    return jsonify({"success": True})

@app.route('/admin/coupons/<code>', methods=['DELETE'])
@app.route('/api/admin/coupons/<code>', methods=['DELETE'])
@require_auth
def admin_delete_coupon(code):
    code = code.upper()
    conn = get_db_connection()
    conn.execute("DELETE FROM coupons WHERE code = ?", (code,))
    conn.commit()
    conn.close()
    audit(g.user.get("sub"), "delete_coupon", "success", {"code": code})
    log_coupon_change(code, "DELETE", {}, g.user.get("sub"))
    return jsonify({"success": True})

@app.route('/admin/coupons/import', methods=['POST'])
@app.route('/api/admin/coupons/import', methods=['POST'])
@require_auth
def admin_import_coupons():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
        
    try:
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        reader = csv.DictReader(stream)
        
        conn = get_db_connection()
        count = 0
        for row in reader:
            code = row.get("code", "").strip().upper()
            if not code: continue
            
            conn.execute("""
                INSERT OR REPLACE INTO coupons (
                    code, discount_type, discount_value, max_uses, used_count, expires_at, min_cart_value, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                code,
                row.get("discount_type", "PERCENT"),
                int(row.get("discount_value", 0)),
                int(row.get("max_uses", -1)),
                int(row.get("used_count", 0)),
                row.get("expires_at") or None,
                int(row.get("min_cart_value", 0)),
                row.get("status", "ACTIVE"),
                now_iso(),
                now_iso()
            ))
            count += 1
            log_coupon_change(code, "IMPORT", row, g.user.get("sub"))
            
        conn.commit()
        conn.close()
        audit(g.user.get("sub"), "import_coupons", "success", {"count": count})
        return jsonify({"success": True, "count": count})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/admin/coupons/export', methods=['GET'])
@app.route('/api/admin/coupons/export', methods=['GET'])
@require_auth
def admin_export_coupons():
    conn = get_db_connection()
    coupons = conn.execute("SELECT * FROM coupons").fetchall()
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['code', 'discount_type', 'discount_value', 'max_uses', 'used_count', 'expires_at', 'min_cart_value', 'status'])
    
    for c in coupons:
        writer.writerow([
            c['code'], c['discount_type'], c['discount_value'], c['max_uses'], 
            c['used_count'], c['expires_at'], c['min_cart_value'], c['status']
        ])
        
    return jsonify({"csv": output.getvalue()})


@app.route('/admin/coupons/<code>/logs', methods=['GET'])
@app.route('/api/admin/coupons/<code>/logs', methods=['GET'])
@require_auth
def admin_get_coupon_logs(code):
    conn = get_db_connection()
    try:
        logs = conn.execute("SELECT * FROM coupon_logs WHERE coupon_code = ? ORDER BY timestamp DESC", (code,)).fetchall()
        return jsonify([dict(row) for row in logs])
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route('/admin/coupons/stats', methods=['GET'])
@app.route('/api/admin/coupons/stats', methods=['GET'])
@require_auth
def admin_coupon_stats():
    conn = get_db_connection()
    try:
        # Total Active Coupons
        active_count = conn.execute("SELECT COUNT(*) as c FROM coupons WHERE status = 'ACTIVE'").fetchone()['c']
        
        # Total Coupons Used (sum of used_count)
        total_uses = conn.execute("SELECT SUM(used_count) as s FROM coupons").fetchone()['s'] or 0
        
        # Total Discount Given
        total_discount = 0
        try:
            total_discount = conn.execute("SELECT SUM(discount_amount) as s FROM orders WHERE status = 'PAID'").fetchone()['s'] or 0
        except Exception:
            pass 
            
        # Top 5 Coupons
        top_coupons = conn.execute("SELECT code, used_count FROM coupons ORDER BY used_count DESC LIMIT 5").fetchall()
        
        return jsonify({
            "active_coupons": active_count,
            "total_uses": total_uses,
            "total_discount_given": total_discount,
            "top_coupons": [dict(row) for row in top_coupons]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


def register_api_aliases():
    existing_rules = {rule.rule for rule in app.url_map.iter_rules()}
    for rule in list(app.url_map.iter_rules()):
        if rule.endpoint == "static":
            continue
        if rule.rule.startswith("/api"):
            continue
        alias = "/api" if rule.rule == "/" else f"/api{rule.rule}"
        if alias in existing_rules:
            continue
        methods = [method for method in rule.methods if method not in {"HEAD", "OPTIONS"}]
        app.add_url_rule(
            alias,
            endpoint=f"api_alias_{rule.endpoint}_{len(existing_rules)}",
            view_func=app.view_functions[rule.endpoint],
            methods=methods
        )
        existing_rules.add(alias)


register_api_aliases()


if __name__ == '__main__':
    logger.info("Starting Payment Server on port 5000...")
    app.run(port=5000, debug=True)
