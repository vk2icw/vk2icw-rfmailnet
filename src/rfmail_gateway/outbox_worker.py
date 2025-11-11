#!/usr/bin/env python3
"""
Outbox queue + retry worker (stdlib only)
- Stages outbound messages to /var/rfmailnet/outbox/<msgid>.json
- Retries with backoff until success or max attempts
"""
from __future__ import annotations
from typing import Dict, Any, Tuple
import os
import json
import time
import threading
import urllib.request
import urllib.error

from .utils import STATE_DIR, save_json, load_json, utc_now_iso
from .index_utils import OUTBOX_DIR, ensure_index_dirs, update_index, mark_state
from .utils import get_route_for  # Uses routes.json

# Config
MAX_ATTEMPTS = 5
BACKOFF_SCHEDULE = [60, 120, 240, 480, 600]  # seconds


def ensure_outbox() -> None:
    ensure_index_dirs()
    os.makedirs(OUTBOX_DIR, exist_ok=True)


def outbox_path(msgid: str) -> str:
    return os.path.join(OUTBOX_DIR, f"{msgid}.json")


def stage_outbound(msg: Dict[str, Any]) -> str:
    """Write/overwrite the outbox file for msgid with scheduling metadata."""
    ensure_outbox()
    msgid = msg.get("msgid", "")
    if not msgid:
        raise ValueError("stage_outbound: msgid required")
    rec = {
        "msg": msg,
        "attempts": 0,
        "next_at": 0,
        "last_error": "",
        "created": utc_now_iso(),
        "updated": utc_now_iso(),
    }
    path = outbox_path(msgid)
    save_json(path, rec)
    update_index(msgid, state="NEW", attempts=0, last_error="")
    return path


def _http_post(url: str, payload: Dict[str, Any], timeout: int = 5) -> Tuple[int, str]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            code = getattr(resp, "status", 200)
            return code, body
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return 0, str(e)


def _next_backoff(attempts: int) -> int:
    if attempts <= 0:
        return BACKOFF_SCHEDULE[0]
    idx = min(attempts, len(BACKOFF_SCHEDULE) - 1)
    return BACKOFF_SCHEDULE[idx]


def _send_once(peer_url: str, msg: Dict[str, Any]) -> Tuple[bool, str]:
    code, body = _http_post(peer_url, msg)
    if code == 200:
        return True, body
    return False, f"{code}:{body}"


def _pick_target_url(msg: Dict[str, Any], default_peer_url: str) -> str:
    dest = msg.get("dest", "")
    url = get_route_for(dest)
    return url or default_peer_url


def process_one(path: str, default_peer_url: str) -> None:
    rec = load_json(path)
    msg = rec.get("msg", {})
    msgid = msg.get("msgid", "")
    if not msgid:
        return

    # honour ttl
    ttl = int(msg.get("ttl", 0))
    if ttl <= 0:
        mark_state(msgid, "FAILED", last_error="TTL_EXPIRED")
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        return

    # decrement TTL before send
    msg = dict(msg)
    msg["ttl"] = ttl - 1

    # compute target
    target = _pick_target_url(msg, default_peer_url)

    ok, info = _send_once(target, msg)
    rec["attempts"] = int(rec.get("attempts", 0)) + 1
    rec["updated"] = utc_now_iso()

    if ok:
        mark_state(msgid, "SENT", attempts=rec["attempts"], last_error="")
        # success → remove from outbox
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
    else:
        rec["last_error"] = info
        if rec["attempts"] >= MAX_ATTEMPTS:
            mark_state(msgid, "FAILED", attempts=rec["attempts"], last_error=info)
            try:
                os.remove(path)
            except FileNotFoundError:
                pass
        else:
            # schedule retry
            delay = _next_backoff(rec["attempts"])
            rec["next_at"] = int(time.time()) + delay
            save_json(path, rec)
            mark_state(msgid, "RETRY", attempts=rec["attempts"], last_error=info)


def worker_loop(default_peer_url: str, interval: int = 15) -> None:
    """Background thread to scan outbox and send due items."""
    ensure_outbox()
    time.sleep(3)
    while True:
        try:
            now = int(time.time())
            for name in list(os.listdir(OUTBOX_DIR)):
                if not name.endswith(".json"):
                    continue
                path = os.path.join(OUTBOX_DIR, name)
                rec = load_json(path)
                next_at = int(rec.get("next_at", 0))
                if next_at and now < next_at:
                    continue  # not due yet
                process_one(path, default_peer_url)
        except Exception as e:
            print(f"outbox worker error: {e}")
        time.sleep(interval)
