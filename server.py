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
from functools import wraps
from flask import Flask, request, jsonify, g
from flask_cors import CORS
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv

load_dotenv()

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


def get_db_connection():
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
    admin = conn.execute("SELECT id FROM admin_users WHERE username = ?", (ADMIN_USERNAME,)).fetchone()
    if not admin:
        conn.execute(
            "INSERT INTO admin_users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
            (ADMIN_USERNAME, hash_password(ADMIN_PASSWORD), "superadmin", now_iso())
        )
    conn.commit()
    conn.close()


init_db()


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
    required = ["nickname", "email", "cpf", "product"]
    missing = [field for field in required if not data.get(field)]
    if missing:
        return False, f"Campos obrigatórios ausentes: {', '.join(missing)}"

    nickname = str(data.get("nickname", "")).strip()
    if not re.fullmatch(r"[a-zA-Z0-9_]{3,16}", nickname):
        return False, "Nickname inválido"

    email = str(data.get("email", "")).strip()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return False, "Email inválido"

    cpf_clean = "".join(filter(str.isdigit, str(data.get("cpf", ""))))
    if len(cpf_clean) != 11:
        return False, "CPF deve conter 11 dígitos"

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
    try:
        conn = get_db_connection()
        heartbeat = _get_latest_connector_heartbeat(conn)
        conn.close()
        return _mc_online_state(heartbeat) != "offline"
    except Exception:
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
            return _parse_iso(row["updated_at"])
    return None


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


@app.route("/")
def home():
    return jsonify({"status": "ok", "service": "Simplex Payment API"})


@app.route("/auth/login", methods=["POST"])
def auth_login():
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
    payload = {"sub": username, "role": user["role"], "iat": now, "exp": now + JWT_EXP_MINUTES * 60}
    token = jwt_encode(payload)
    audit(username, "auth_login", "success")
    return jsonify({"token": token, "expires_in": JWT_EXP_MINUTES * 60, "role": user["role"]})


@app.route("/auth/me", methods=["GET"])
@require_auth
def auth_me():
    return jsonify({"username": g.user.get("sub"), "role": g.user.get("role")})


@app.route('/create-payment', methods=['POST'])
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
    payload = {
        "frequency": "ONE_TIME",
        "methods": ["PIX"],
        "products": [{"externalId": product_name, "name": f"VIP {product_name}", "quantity": 1, "price": amount, "description": f"VIP {product_name} para {nickname}"}],
        "returnUrl": os.getenv("RETURN_URL", "http://localhost:5500/success"),
        "completionUrl": os.getenv("COMPLETION_URL", "http://localhost:5500/success"),
        "customer": {"name": nickname, "email": email, "taxId": cpf_clean, "cellphone": sanitize_phone(data.get("cellphone"))}
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
            "INSERT OR IGNORE INTO orders (id, customer_name, customer_email, customer_cpf, product, amount, status, delivery_status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (bill_id, nickname, email, cpf_clean, product_name, amount, "PENDING", "PENDING", now_iso(), now_iso())
        )
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
    payload = {
        "amount": amount,
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
        "INSERT OR IGNORE INTO orders (id, customer_name, customer_email, customer_cpf, product, amount, status, delivery_status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (pix_id, nickname, email, cpf_clean, product_name, amount, "PENDING", "PENDING", now_iso(), now_iso())
    )
    conn.commit()
    conn.close()
    return jsonify({"brCode": data_obj.get("brCode"), "brCodeBase64": data_obj.get("brCodeBase64"), "pixId": pix_id})


@app.route('/webhook/abacate', methods=['POST'])
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
        delivery_status = "DELIVERED" if delivered else "ROLLBACK_PENDING"
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
    payload = {"api_status": "online", "db_status": "online", "mc_status": "offline", "payment_status": "online" if ABACATE_API_TOKEN else "warning"}
    try:
        conn = get_db_connection()
        conn.execute("SELECT 1").fetchone()
        heartbeat = _get_latest_connector_heartbeat(conn)
        conn.close()
        payload["mc_status"] = _mc_online_state(heartbeat)
    except Exception:
        payload["db_status"] = "offline"
        payload["mc_status"] = "offline"
    return payload


@app.route('/admin/stats', methods=['GET'])
@require_auth
def admin_stats():
    days = int(request.args.get("days", "30"))
    audit(g.user.get("sub"), "admin_stats", "success", {"days": days})
    return jsonify(_stats_payload(days))


@app.route('/admin/status', methods=['GET'])
@require_auth
def admin_status():
    audit(g.user.get("sub"), "admin_status", "success")
    return jsonify(_status_payload())


@app.route('/admin/audit', methods=['GET'])
@require_auth
def admin_audit():
    limit = min(int(request.args.get("limit", "100")), 300)
    conn = get_db_connection()
    rows = conn.execute("SELECT actor, action, status, ip, metadata, created_at FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return jsonify({"logs": [dict(row) for row in rows]})


@app.route('/connector/events', methods=['POST'])
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
    conn.execute(
        "INSERT OR REPLACE INTO connector_cache (cache_key, payload, updated_at) VALUES (?, ?, ?)",
        (f"{g.user.get('sub')}:{int(time.time() * 1000)}", json.dumps({"type": event_type, "payload": payload}), now_iso())
    )
    conn.commit()
    conn.close()
    audit(g.user.get("sub"), "connector_events", "success", {"type": event_type})
    return jsonify({"success": True})


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


if __name__ == '__main__':
    logger.info("Starting Payment Server on port 5000...")
    app.run(port=5000, debug=True)
