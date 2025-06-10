import os
from datetime import datetime

def ensure_dir_exists(path: str):
    if not os.path.exists(path):
        os.makedirs(path)

def current_timestamp_iso():
    return datetime.utcnow().isoformat()

def log_debug(label: str, value: str):
    print(f"[DEBUG] {label}: {str(value)[:200]}")
