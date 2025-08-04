# utils/structured_logger.py

import json
from pathlib import Path
from datetime import datetime
import threading
import shutil

LOG_DIR = Path("data/logs")
LOG_FILE = LOG_DIR / "structured_calls.ndjson"
ROTATED_DIR = LOG_DIR / "archived"
MAX_BYTES = 5 * 1024 * 1024  # 5 MB before rotation; adjust as needed

_lock = threading.Lock()
LOG_DIR.mkdir(parents=True, exist_ok=True)
ROTATED_DIR.mkdir(parents=True, exist_ok=True)


def _rotate_if_needed():
    try:
        if LOG_FILE.exists() and LOG_FILE.stat().st_size >= MAX_BYTES:
            timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
            archived = ROTATED_DIR / f"structured_calls_{timestamp}.ndjson"
            shutil.move(str(LOG_FILE), str(archived))
            # Optionally compress archived log (skip for simplicity)
    except Exception:
        # rotation must not break logging
        pass


def log_event(call_id: str, step: str, input_data=None, output_data=None, outcome: str = "ok", extra: dict | None = None):
    """
    Appends a structured event as a single line JSON (NDJSON). Thread-safe.
    """
    entry = {
        "call_id": call_id,
        "step": step,
        "input": input_data,
        "output": output_data,
        "outcome": outcome,
        "extra": extra or {},
        "timestamp": datetime.utcnow().isoformat(),
    }
    line = json.dumps(entry, ensure_ascii=False)
    with _lock:
        _rotate_if_needed()
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def redact_phone(number: str):
    if len(number) >= 4:
        return "***-***-" + number[-4:]
    return number


def read_events(call_id: str = None, limit: int = 100):
    """
    Reads the last `limit` events, optionally filtered by call_id.
    """
    if not LOG_FILE.exists():
        return []

    results = []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if call_id is None or obj.get("call_id") == call_id:
                results.append(obj)
    return results[-limit:]
