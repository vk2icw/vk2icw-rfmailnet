#!/usr/bin/env python3
import json
import os
import requests
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

VERSION = "0.7"
INBOX_DIR = "/var/rfmailnet/inbox"
SEEN_FILE = "/var/rfmailnet/seen.json"
ROUTES_FILE = "/var/rfmailnet/routes.json"
PEER_URL = "http://10.44.0.1:8080"  # 🔁 Pi → VPS (change on VPS to 10.44.0.2)
DEFAULT_TTL = 5
HELLO_INTERVAL = 120  # seconds
ROUTE_EXPIRY = 600    # seconds before a route is considered stale

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------
def load_json(path, default):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def load_seen():
    return set(load_json(SEEN_FILE, []))

def save_seen(seen):
    save_json(SEEN_FILE, list(seen))

def load_routes():
    return load_json(ROUTES_FILE, {})

def save_routes(routes):
    save_json(ROUTES_FILE, routes)

# ---------------------------------------------------------------------------
# Auto-discovery subsystem
# ---------------------------------------------------------------------------
NODE_ID = os.uname()[1].upper()  # use hostname as node ID

def cleanup_routes():
    """Remove routes older than ROUTE_EXPIRY seconds."""
    routes = load_routes()
    now = time.time()
    changed = False
    for node, info in list(routes.items()):
        if now - info.get("ts", 0) > ROUTE_EXPIRY:
            print(f"🧹 Expired route to {node}")
            del routes[node]
            changed = True
    if changed:
        save_routes(routes)

def broadcast_hello():
    """Send HELLO packets periodically to announce our presence."""
    while True:
        routes = load_routes()
        routes[NODE_ID] = {"addr": f"http://{os.uname()[1]}:8080", "ts": time.time()}
        save_routes(routes)
        hello = {
            "type": "HELLO",
            "node": NODE_ID,
            "address": f"http://{os.uname()[1]}:8080",
            "timestamp": time.time(),
            "routes": list(routes.keys()),
        }
        try:
            requests.post(PEER_URL, json=hello, timeout=5)
            print(f"📡 Sent HELLO to {PEER_URL}")
        except Exception as e:
            print(f"⚠️ HELLO failed: {e}")
        cleanup_routes()
        time.sleep(HELLO_INTERVAL)

def handle_hello(msg, client_ip=None):
    """Process incoming HELLO and update routes."""
    if msg.get("type") != "HELLO":
        return False
    routes = load_routes()
    routes[msg["node"]] = {
        "addr": msg.get("address"),
        "ts": msg.get("timestamp"),
        "via": client_ip,
    }
    save_routes(routes)
    print(f"🤝 Learned route to {msg['node']} via {client_ip}")
    return True

# ---------------------------------------------------------------------------
# Main HTTP handler
# ---------------------------------------------------------------------------
class RFMailHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        msg = {
            "status": "OK",
            "node": NODE_ID,
            "version": VERSION,
            "peer": PEER_URL,
            "routes": list(load_routes().keys()),
        }
        self.wfile.write(json.dumps(msg).encode())

    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            content_length = 0
        body = self.rfile.read(content_length).decode(errors="replace")

        try:
            msg = json.loads(body)

            # Handle HELLO packets
            if msg.get("type") == "HELLO":
                handle_hello(msg, self.client_address[0])
                return self._reply({"status": "ack"})

            msgid = str(msg.get("msgid", "unknown")).strip() or "unknown"
            dest = msg.get("dest", "UNKNOWN")

            # Loop prevention
            seen = load_seen()
            if msgid in seen:
                print(f"🔁 Ignoring duplicate {msgid}")
                return self._reply({"status": "ignored"})
            seen.add(msgid)
            save_seen(seen)

            # TTL
            ttl = msg.get("ttl", DEFAULT_TTL)
            if not isinstance(ttl, int):
                ttl = DEFAULT_TTL
            ttl -= 1
            msg["ttl"] = ttl
            if ttl < 0:
                print(f"🕑 Dropped {msgid} (expired TTL)")
                return self._reply({"status": "expired"})

            # Save locally
            os.makedirs(INBOX_DIR, exist_ok=True)
            path = os.path.join(INBOX_DIR, f"{msgid}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(msg, f, indent=2)
            print(f"📬 Stored message {msgid} for {dest} (TTL={ttl})")

            # Forward if needed
            if ttl > 0:
                self.route_forward(msg, dest)
            else:
                print(f"🛑 TTL=0, not forwarding {msgid}")

            self._reply({"status": "saved", "msgid": msgid, "ttl": ttl})

        except Exception as e:
            print(f"❌ Error: {e}")
            self._reply({"status": "error", "error": str(e)})

    # -----------------------------------------------------------------------
    def route_forward(self, msg, dest):
        """Forward using discovered routes."""
        routes = load_routes()
        if dest in routes:
            target = routes[dest]["addr"]
            print(f"➡️ Routing {msg['msgid']} → {dest} via {target}")
        else:
            target = PEER_URL
            print(f"➡️ Routing {msg['msgid']} → unknown dest, using default {target}")

        try:
            r = requests.post(target, json=msg, timeout=5)
            if r.status_code == 200:
                print(f"✅ Delivered {msg['msgid']} (TTL={msg['ttl']})")
            else:
                print(f"⚠️ Route failed ({r.status_code}): {r.text}")
        except Exception as e:
            print(f"❌ Route error: {e}")

    # -----------------------------------------------------------------------
    def _reply(self, payload):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())

    def log_message(self, format, *args):
        return  # silence default logs


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print(f"🛰 RFMailNet Gateway v{VERSION} starting...")
    print(f"Listening on http://0.0.0.0:8080")
    print(f"Forwarding peer: {PEER_URL}")

    os.makedirs(INBOX_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(SEEN_FILE), exist_ok=True)
    os.makedirs(os.path.dirname(ROUTES_FILE), exist_ok=True)

    threading.Thread(target=broadcast_hello, daemon=True).start()

    server = HTTPServer(("", 8080), RFMailHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 RFMailNet Gateway stopped.")
    finally:
        server.server_close()
