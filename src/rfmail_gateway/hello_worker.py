import threading
import time
import requests
import json
import os
from datetime import datetime
from rfmail_gateway.index_utils import save_json_atomic

ROUTES_FILE = "/var/rfmailnet/routes.json"
HELLO_INTERVAL = 60  # seconds

def send_hello(peer_url, node_name, version):
    data = {
        "type": "HELLO",
        "node": node_name,
        "version": version,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    try:
        response = requests.post(peer_url, json=data, timeout=5)
        if response.status_code == 200:
            print(f"📡 Sent HELLO → {peer_url} (200)")
            return True
        else:
            print(f"⚠️ HELLO to {peer_url} failed: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"⚠️ HELLO to {peer_url} failed: {e}")
        return False


def start_hello_thread(peer_url, node_name, version):
    def hello_loop():
        while True:
            success = send_hello(peer_url, node_name, version)
            now = datetime.utcnow().isoformat() + "Z"
            routes = {}

            if os.path.exists(ROUTES_FILE):
                try:
                    with open(ROUTES_FILE, "r") as f:
                        routes = json.load(f)
                except json.JSONDecodeError:
                    routes = {}

            # Update self record (for status tracking)
            routes[node_name] = {
                "addr": f"http://{node_name.lower()}:8080",
                "ts": time.time(),
                "version": version
            }

            # Update peer record if HELLO succeeded
            peer_node = "REMOTE" if "SERVER" in node_name else "SERVER"
            if success:
                routes[peer_node] = {
                    "addr": peer_url,
                    "ts": now,
                    "via": peer_url.split("/")[2].split(":")[0],
                    "status": "online"
                }
            else:
                routes[peer_node] = {
                    "addr": peer_url,
                    "ts": now,
                    "via": peer_url.split("/")[2].split(":")[0],
                    "status": "offline"
                }

            save_json_atomic(ROUTES_FILE, routes)
            time.sleep(HELLO_INTERVAL)

    thread = threading.Thread(target=hello_loop, daemon=True)
    thread.start()
    print(f"🚀 HELLO thread started ({peer_url})")
