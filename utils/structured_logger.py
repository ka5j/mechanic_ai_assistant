# utils/structured_logger.py

import json
import threading
from datetime import datetime
from pathlib import Path
from core.paths import STRUCT_LOG_FILE as LOG_FILE, STRUCT_LOG_ARCHIVE as ARCHIVE_DIR

_lock = threading.Lock()

def _rotate_if_needed():
    """
    If LOG_FILE exceeds 5MB, move it into ARCHIVE_DIR (timestamped)
    and start a fresh empty log file.
    """
    log_path = Path(LOG_FILE)
    archive_dir = Path(ARCHIVE_DIR)
    archive_dir.mkdir(parents=True, exist_ok=True)

    if log_path.exists() and log_path.stat().st_size > 5 * 1024 * 1024:
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        archived = archive_dir / f"structured_calls_{ts}.ndjson"
        log_path.rename(archived)
        log_path.write_text("", encoding="utf-8")

def log_event(
    call_id: str,
    step: str,
    input_data=None,
    output_data=None,
    outcome: str = "ok",
    extra: dict | None = None
):
    """
    Append a single NDJSON line to LOG_FILE.
    Auto-creates parent directories and rotates if too large.
    """
    log_path = Path(LOG_FILE)
    log_path.parent.mkdir(parents=True, exist_ok=True)

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
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

def read_events() -> list[dict]:
    """
    Read all JSON lines from LOG_FILE and return them as a list of dicts.
    """
    log_path = Path(LOG_FILE)
    if not log_path.exists():
        return []
    lines = log_path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]
