#!/usr/bin/env python3
import json
import os
import time
import threading
import requests

INBOX_DIR = "/var/rfmailnet/inbox"
ROUTES_FILE = "/var/rfmailnet/routes.json"
SEEN_FILE = "/var/rfmailnet/seen.json"
FORWARD_INTERVAL = 15  # seconds

def start_relay_thread(peer_url, node_name):
    """Starts a background thread to forward pending messages."""
    thread = threading.Thread(target=_relay_loop, args=(peer_url, node_name), daemon=True)
    thread.start()
    return thread

def _relay_loop(peer_url, node_name):
    """Periodically check inbox for unsent messages and forward them."""
    print(f"📡 Relay thread started for {node_name} → {peer_url}")
    os.makedirs(INBOX_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(SEEN_FILE), exist_ok=True)

    while True:
        try:
            for filename in os.listdir(INBOX_DIR):
                if not filename.endswith(".json"):
                    continue

                filepath = os.path.join(INBOX_DIR, filename)
                with open(filepath, "r") as f:
                    msg = json.load(f)

                msgid = msg.get("msgid", "unknown")
                ttl = msg.get("ttl", 0)

                # Skip expired messages
                if ttl <= 0:
                    continue

                # Decrement TTL before forwarding
                msg["ttl"] = ttl - 1

                # Forward to peer
                try:
                    resp = requests.post(peer_url, json=msg, timeout=10)
                    if resp.status_code == 200:
                        print(f"🚀 Relayed {msgid} → {peer_url} (TTL={msg['ttl']})")
                except Exception as e:
                    print(f"⚠️ Relay error for {msgid}: {e}")

        except Exception as e:
            print(f"❌ Relay loop error: {e}")

        time.sleep(FORWARD_INTERVAL)
