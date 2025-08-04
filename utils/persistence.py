# utils/persistence.py

import json
from pathlib import Path
from datetime import datetime
import threading

_lock = threading.Lock()

def _atomic_write(path: Path, data: str):
    tmp = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(data)
        f.flush()
    tmp.replace(path)

def append_json_entry(path: Path, entry: dict):
    with _lock:
        existing = []
        if path.exists():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(existing, list):
                    existing = []
            except Exception:
                existing = []
        existing.append(entry)
        _atomic_write(path, json.dumps(existing, default=str, indent=2))

def persist_appointment(summary: dict, path: str = "data/calendar/appointments.json"):
    """
    summary: {
      "call_id": str,
      "service": str,
      "date": "YYYY-MM-DD",
      "time": "HH:MM",
      "duration_minutes": int,
      "created_at": iso-timestamp
    }
    """
    append_json_entry(Path(path), summary)

def persist_call_session(session, path: str = "data/calls/calls.json"):
    """
    session: CallSession instance with attributes:
      - call_id
      - caller_number
      - state (dict)
      - history (list)
      - escalation_triggered (bool)
    """
    entry = {
        "call_id": session.call_id,
        "caller_number": session.caller_number,
        "state": session.state,
        "history": getattr(session, "history", None),
        "escalation_triggered": getattr(session, "escalation_triggered", False),
        "created_at": datetime.now().isoformat(),
    }
    append_json_entry(Path(path), entry)

def persist_usage(call_id: str, total_tokens: int, path: str = "data/usage.json"):
    """
    call_id: the session ID
    total_tokens: number of tokens used in the LLM call
    """
    entry = {
        "call_id": call_id,
        "tokens": total_tokens,
        "timestamp": datetime.now().isoformat(),
    }
    append_json_entry(Path(path), entry)
