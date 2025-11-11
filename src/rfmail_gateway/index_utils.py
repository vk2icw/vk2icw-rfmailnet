import os
import json
import tempfile
from datetime import datetime

def ensure_dir(path):
    """Ensure a directory exists."""
    os.makedirs(path, exist_ok=True)

def load_json(path, default=None):
    """Load JSON safely, returning default on failure."""
    if not os.path.exists(path):
        return default
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, data):
    """Save JSON to file with indentation."""
    try:
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"⚠️ Failed to save JSON to {path}: {e}")

def timestamp_utc():
    """Return a UTC timestamp string."""
    return datetime.utcnow().isoformat() + "Z"

def list_json_files(directory):
    """List all JSON files in a directory."""
    try:
        return [f for f in os.listdir(directory) if f.endswith('.json')]
    except FileNotFoundError:
        return []

def append_log_line(file_path, message):
    """Append a timestamped line to a log file."""
    with open(file_path, "a") as f:
        f.write(f"[{datetime.utcnow().isoformat()}Z] {message}\n")

# --- New atomic JSON saver (added for HELLO + route updates) ---

def save_json_atomic(path, data):
    """Safely save JSON atomically: write → flush → rename."""
    directory = os.path.dirname(path)
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)

    tmp_fd, tmp_path = tempfile.mkstemp(dir=directory)
    try:
        with os.fdopen(tmp_fd, 'w') as tmp_file:
            json.dump(data, tmp_file, indent=2)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
        os.replace(tmp_path, path)
    except Exception as e:
        print(f"⚠️ Failed atomic save to {path}: {e}")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
