# utils/usage_guard.py

import json
from pathlib import Path
from core.paths import USAGE_JSON_PATH as USAGE_FILE

def load_usage() -> dict:
    """
    Load the cumulative token-usage record.
    If the file doesn’t exist, initialize it to {"tokens": 0}.
    """
    path = Path(USAGE_FILE)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"tokens": 0}), encoding="utf-8")
    return json.loads(path.read_text(encoding="utf-8"))

def save_usage(data: dict):
    """
    Overwrite the usage file with `data`.
    """
    path = Path(USAGE_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def can_call_model() -> bool:
    """
    Return False if total tokens exceed your configured limit.
    """
    usage = load_usage()
    # Example limit; replace with your actual config
    limit = 100_000
    return usage.get("tokens", 0) < limit

def record_usage(tokens_used: int):
    """
    Increment the total usage counter by tokens_used.
    """
    data = load_usage()
    data["tokens"] = data.get("tokens", 0) + tokens_used
    save_usage(data)
