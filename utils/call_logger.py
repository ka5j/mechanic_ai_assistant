# utils/call_logger.py

import os
import json
from datetime import datetime
from pathlib import Path

LOG_DIR = Path("data/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

def log_call_start(phone_number):
    call_id = f"{phone_number.replace('+', '').replace('-', '')}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    log_file = LOG_DIR / f"{call_id}.json"
    data = {
        "call_id": call_id,
        "phone_number": phone_number,
        "start_time": datetime.now().isoformat(),
        "events": []
    }
    with open(log_file, "w") as f:
        json.dump(data, f, indent=4)
    return call_id, datetime.now()

def log_call_end(call_id):
    log_file = LOG_DIR / f"{call_id}.json"
    if not log_file.exists():
        return
    with open(log_file, "r+") as f:
        data = json.load(f)
        data["end_time"] = datetime.now().isoformat()
        f.seek(0)
        json.dump(data, f, indent=4)
        f.truncate()

def log_interaction(event_type, payload):
    """
    Generic logger used by assistant.py to log AI interactions and errors.
    """
    current_log_files = sorted(LOG_DIR.glob("*.json"), reverse=True)
    if not current_log_files:
        return
    log_file = current_log_files[0]

    with open(log_file, "r+") as f:
        data = json.load(f)
        data.setdefault("events", []).append({
            "timestamp": datetime.now().isoformat(),
            "event": event_type,
            "payload": payload
        })
        f.seek(0)
        json.dump(data, f, indent=4)
        f.truncate()
