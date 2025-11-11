#!/usr/bin/env python3
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime

from rfmail_gateway.hello_worker import start_hello_thread

VERSION = "0.8-pre"
INBOX_DIR = "/var/rfmailnet/inbox"
ROUTES_FILE = "/var/rfmailnet/routes.json"
SEEN_FILE = "/var/rfmailnet/seen.json"


class RFMailHandler(BaseHTTPRequestHandler):
    def _set_headers(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

    def do_GET(self):
        """Respond to basic status checks"""
        self._set_headers()
        message = {
            "status": "OK",
            "node": "VK2ICW-PI",
            "version": VERSION,
            "inbox": INBOX_DIR,
            "routes": ROUTES_FILE,
            "seen": SEEN_FILE,
            "peer_url": "http://10.44.0.1:8080"
        }
        self.wfile.write(json.dumps(message).encode())

    def do_POST(self):
        """Receive incoming messages or HELLO packets"""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode()

        try:
            msg = json.loads(body)
            msg_type = msg.get("type", "MSG")

            if msg_type == "HELLO":
                # Handle HELLO message
                self.handle_hello(msg)
                response = {"status": "hello_received", "node": msg.get("node")}
            else:
                # Handle normal RFMail message
                msgid = msg.get("msgid", f"unknown-{datetime.utcnow().timestamp()}")
                os.makedirs(INBOX_DIR, exist_ok=True)
                filename = os.path.join(INBOX_DIR, f"{msgid}.json")

                with open(filename, "w") as f:
                    json.dump(msg, f, indent=2)

                print(f"📬 Saved RFMail message {msgid} to {filename}")
                response = {"status": "saved", "msgid": msgid}

        except Exception as e:
            print(f"❌ Error handling POST: {e}")
            response = {"status": "error", "error": str(e)}

        self._set_headers()
        self.wfile.write(json.dumps(response).encode())

    def handle_hello(self, msg):
        """Update routes.json when HELLO received"""
        try:
            node = msg.get("node", "unknown")
            routes = {}
            if os.path.exists(ROUTES_FILE):
                with open(ROUTES_FILE, "r") as f:
                    routes = json.load(f)

            routes[node] = {
                "last_seen": msg.get("timestamp", datetime.utcnow().isoformat() + "Z"),
                "version": msg.get("version", "unknown")
            }

            os.makedirs(os.path.dirname(ROUTES_FILE), exist_ok=True)
            with open(ROUTES_FILE, "w") as f:
                json.dump(routes, f, indent=2)

            print(f"🤝 HELLO received from {node}")
        except Exception as e:
            print(f"⚠️ Failed to handle HELLO: {e}")


def run_gateway():
    """Start RFMailNet gateway and HELLO thread"""
    server = HTTPServer(("0.0.0.0", 8080), RFMailHandler)
    print(f"🛰 RFMailNet Gateway v{VERSION} (VK2ICW-PI) running on http://0.0.0.0:8080")

    # Start periodic HELLO broadcast to VPS peer
    peer_url = "http://10.44.0.1:8080"  # VPS IP
    start_hello_thread(peer_url, "VK2ICW-PI", VERSION)

    server.serve_forever()


if __name__ == "__main__" or __name__ == "rfmail_gateway.main":
    run_gateway()
