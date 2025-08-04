# utils/structured_logger.py

import json
from pathlib import Path
from datetime import datetime

LOG_FILE = Path("data/logs/structured_calls.json")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

def _load():
    if LOG_FILE.exists():
        try:
            with open(LOG_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {"calls": []}
    return {"calls": []}

def _save(data):
    with open(LOG_FILE, "w") as f:
        json.dump(data, f, indent=2)

def log_event(call_id: str, step: str, input_data=None, output_data=None, outcome: str = "ok", extra: dict | None = None):
    data = _load()
    entry = {
        "call_id": call_id,
        "step": step,
        "input": input_data,
        "output": output_data,
        "outcome": outcome,
        "extra": extra or {},
        "timestamp": datetime.utcnow().isoformat(),
    }
    data.setdefault("calls", []).append(entry)
    _save(data)

def redact_phone(number: str):
    if len(number) >= 4:
        return "***-***-" + number[-4:]
    return number
