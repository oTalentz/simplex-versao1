import os
import ssl
import json
import time
import queue
import hmac
import base64
import hashlib
import threading
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class SimplexConnector:
    def __init__(self):
        self.api_url = os.getenv("CONNECTOR_API_URL", "https://localhost:5000")
        self.ws_url = os.getenv("CONNECTOR_WS_URL", "wss://localhost:5000/ws")
        self.jwt_secret = os.getenv("JWT_SECRET", "simplex_dev_secret_change_me")
        self.agent_id = os.getenv("CONNECTOR_AGENT_ID", "simplex-agent-01")
        self.cache_file = os.getenv("CONNECTOR_CACHE_FILE", "connector_cache.json")
        self.sync_interval = int(os.getenv("CONNECTOR_SYNC_INTERVAL", "8"))
        self.max_retry = int(os.getenv("CONNECTOR_MAX_RETRY", "5"))
        self.cache_ttl_seconds = int(os.getenv("CONNECTOR_CACHE_TTL_SECONDS", "86400"))
        self.buffer = queue.Queue()
        self.running = False
        self.session = self._build_session()

    def _build_session(self):
        session = requests.Session()
        retry = Retry(total=self.max_retry, backoff_factor=0.7, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET", "POST"])
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def _token(self):
        header = self._b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode("utf-8"))
        now = int(time.time())
        payload = self._b64(json.dumps({"sub": self.agent_id, "iat": now, "exp": now + 3600}).encode("utf-8"))
        signature = hmac.new(self.jwt_secret.encode("utf-8"), f"{header}.{payload}".encode("utf-8"), hashlib.sha256).digest()
        return f"{header}.{payload}.{self._b64(signature)}"

    def _b64(self, value):
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode("utf-8")

    def _headers(self):
        return {"Authorization": f"Bearer {self._token()}", "Content-Type": "application/json"}

    def _load_cache(self):
        if not os.path.exists(self.cache_file):
            return []
        with open(self.cache_file, "r", encoding="utf-8") as file:
            raw = json.load(file)
        now = int(time.time())
        valid_items = []
        for item in raw:
            timestamp = int(item.get("timestamp", 0))
            if now - timestamp <= self.cache_ttl_seconds:
                valid_items.append(item)
        if len(valid_items) != len(raw):
            self._save_cache(valid_items)
        return valid_items

    def _save_cache(self, items):
        with open(self.cache_file, "w", encoding="utf-8") as file:
            json.dump(items, file, ensure_ascii=False)

    def _cache_event(self, event):
        items = self._load_cache()
        cached = dict(event)
        cached["timestamp"] = int(cached.get("timestamp", int(time.time())))
        items.append(cached)
        self._save_cache(items)

    def _send_https(self, event):
        endpoint = f"{self.api_url}/connector/events"
        response = self.session.post(endpoint, json=event, headers=self._headers(), timeout=10, verify=True)
        if not response.ok:
            raise RuntimeError(f"HTTP {response.status_code}")

    def _sync_cache(self):
        items = self._load_cache()
        if not items:
            return
        pending = []
        for item in items:
            try:
                self._send_https(item)
            except Exception:
                pending.append(item)
        self._save_cache(pending)

    def emit(self, event_type, payload):
        event = {"type": event_type, "payload": payload, "timestamp": int(time.time())}
        self.buffer.put(event)

    def _ws_loop(self):
        try:
            import websocket
        except Exception:
            return
        while self.running:
            token = self._token()
            headers = [f"Authorization: Bearer {token}"]
            ws = None
            try:
                ws = websocket.create_connection(self.ws_url, header=headers, timeout=8, sslopt={"cert_reqs": ssl.CERT_REQUIRED})
                while self.running:
                    try:
                        event = self.buffer.get(timeout=self.sync_interval)
                        ws.send(json.dumps(event))
                    except queue.Empty:
                        self._sync_cache()
            except Exception:
                time.sleep(2)
            finally:
                if ws:
                    ws.close()

    def _https_loop(self):
        while self.running:
            try:
                event = self.buffer.get(timeout=self.sync_interval)
                self._send_https(event)
            except queue.Empty:
                try:
                    self._sync_cache()
                except Exception:
                    pass
            except Exception:
                self._cache_event(event)
                time.sleep(1)

    def start(self):
        self.running = True
        self._sync_cache()
        threading.Thread(target=self._https_loop, daemon=True).start()
        threading.Thread(target=self._ws_loop, daemon=True).start()

    def stop(self):
        self.running = False


if __name__ == "__main__":
    connector = SimplexConnector()
    connector.start()
    connector.emit("heartbeat", {"agent": connector.agent_id})
    while True:
        time.sleep(10)
        connector.emit("heartbeat", {"agent": connector.agent_id})
