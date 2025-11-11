#!/usr/bin/env python3
"""
Utility functions for RFMailNet
"""
import json, os, time, datetime
from typing import Any, Dict

STATE_DIR = "/var/rfmailnet"
INBOX_DIR = os.path.join(STATE_DIR, "inbox")
ROUTES_PATH = os.path.join(STATE_DIR, "routes.json")
SEEN_PATH = os.path.join(STATE_DIR, "seen.json")


def ensure_dirs():
    for p in [STATE_DIR, INBOX_DIR]:
        os.makedirs(p, exist_ok=True)
    if not os.path.exists(SEEN_PATH):
        save_json(SEEN_PATH, [])
    if not os.path.exists(ROUTES_PATH):
        save_json(ROUTES_PATH, {})


def load_json(path: str) -> Any:
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return {} if path.endswith(".json") else []


def save_json(path: str, obj: Any) -> None:
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)


def utc_now_iso() -> str:
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def add_seen(msgid: str):
    seen = load_json(SEEN_PATH)
    if msgid not in seen:
        seen.append(msgid)
        save_json(SEEN_PATH, seen)


def is_seen(msgid: str) -> bool:
    seen = load_json(SEEN_PATH)
    return msgid in seen


def update_route(node: str, **fields):
    routes = load_json(ROUTES_PATH)
    rec = routes.get(node, {})
    rec.update(fields)
    rec["updated"] = utc_now_iso()
    routes[node] = rec
    save_json(ROUTES_PATH, routes)


def get_route_for(node: str) -> str:
    routes = load_json(ROUTES_PATH)
    return routes.get(node, {}).get("url", "")


def expire_routes(age: int = 900):
    routes = load_json(ROUTES_PATH)
    now = time.time()
    changed = False
    for node, rec in list(routes.items()):
        updated = rec.get("updated")
        if not updated:
            continue
        try:
            ts = datetime.datetime.fromisoformat(updated.rstrip("Z")).timestamp()
            if now - ts > age:
                del routes[node]
                changed = True
        except Exception:
            pass
    if changed:
        save_json(ROUTES_PATH, routes)
