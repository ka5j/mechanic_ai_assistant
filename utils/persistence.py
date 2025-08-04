# utils/persistence.py

import json
from datetime import datetime
from pathlib import Path
from core.paths import CALLS_JSON_PATH as CALLS_FILE, USAGE_JSON_PATH as USAGE_FILE
from assistant.session import CallSession

def load_calls() -> list[dict]:
    """
    Load persisted call/session records from CALLS_FILE.
    Returns an empty list if none exist.
    """
    path = Path(CALLS_FILE)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("[]", encoding="utf-8")
    return json.loads(path.read_text(encoding="utf-8"))

def _serialize_session(session: CallSession) -> dict:
    """
    Turn a CallSession into a JSON-serializable dict.
    """
    return {
        "call_id": session.call_id,
        "caller_number": session.caller_number,
        "state": session.state,
        "history": session.history,
        "created_at": datetime.utcnow().isoformat()
    }

def persist_call_session(record):
    """
    Append a call/session record to CALLS_FILE.
    Accepts either:
      - a CallSession instance, or
      - a plain dict.
    """
    path = Path(CALLS_FILE)
    calls = load_calls()

    if isinstance(record, CallSession):
        entry = _serialize_session(record)
    elif isinstance(record, dict):
        entry = record.copy()
        entry.setdefault("created_at", datetime.utcnow().isoformat())
    else:
        raise TypeError("persist_call_session expects a CallSession or dict")

    calls.append(entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(calls, ensure_ascii=False, indent=2), encoding="utf-8")

def persist_appointment(appointment_data: dict):
    """
    Alias for appointments if you treat them separately.
    Just reuses call-session persistence by default.
    """
    persist_call_session(appointment_data)

def load_usage_events() -> list[dict]:
    """
    Load per-call usage events from USAGE_FILE.
    Returns an empty list if none exist.
    """
    path = Path(USAGE_FILE)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("[]", encoding="utf-8")
    return json.loads(path.read_text(encoding="utf-8"))

def persist_usage(call_id: str, tokens_used: int):
    """
    Append a usage event (with call_id, token count, timestamp) to USAGE_FILE.
    """
    path = Path(USAGE_FILE)
    events = load_usage_events()
    events.append({
        "call_id": call_id,
        "tokens": tokens_used,
        "timestamp": datetime.utcnow().isoformat()
    })
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
