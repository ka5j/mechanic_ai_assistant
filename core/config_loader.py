# core/config_loader.py

import json
from pathlib import Path
from dotenv import load_dotenv
import os
from core.config_schema import RootConfig
import re
from datetime import datetime

# Path constants (adjust if your layout differs)
DEFAULT_CONFIG_PATH = Path("config/demo_config.json")
DEFAULT_ENV_PATH = Path("secrets/.env")


def parse_business_hours_string(s: str):
    """
    Given a string like "8:00 AM - 6:00 PM", returns (open_24, close_24) e.g. ("08:00","18:00").
    """
    try:
        parts = s.split("-")
        if len(parts) != 2:
            raise ValueError(f"Cannot parse hours string: {s}")
        open_part = parts[0].strip()
        close_part = parts[1].strip()
        open_dt = datetime.strptime(open_part, "%I:%M %p")
        close_dt = datetime.strptime(close_part, "%I:%M %p")
        return open_dt.strftime("%H:%M"), close_dt.strftime("%H:%M")
    except Exception as e:
        raise ValueError(f"Failed to normalize business hours '{s}': {e}") from e


def normalize_hours(raw_hours):
    """
    If raw_hours is a dict of day->range strings (e.g., "Monday": "8:00 AM - 6:00 PM"),
    extract an open and close time (uses Monday if present, else first parsable entry).
    If already in expected shape with 'open'/'close', return as-is.
    """
    if isinstance(raw_hours, dict):
        # If it's already the desired shape, leave it
        if "open" in raw_hours and "close" in raw_hours:
            return raw_hours
        # Prefer Monday, else first key
        key = "Monday" if "Monday" in raw_hours else next(iter(raw_hours))
        hours_str = raw_hours.get(key)
        if not hours_str or "closed" in str(hours_str).lower():
            # fallback to default business hours
            return {"open": "09:00", "close": "17:00"}
        open_t, close_t = parse_business_hours_string(hours_str)
        return {"open": open_t, "close": close_t}
    # Unexpected format; fallback to defaults
    return {"open": "09:00", "close": "17:00"}


def load_raw_config(path: Path = DEFAULT_CONFIG_PATH) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found at {path.resolve()}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_config() -> RootConfig:
    """
    Loads environment variables and the JSON config, normalizes legacy formats,
    validates against schema, and returns a typed RootConfig instance.
    """
    # Load .env early so any env overrides are present
    if DEFAULT_ENV_PATH.exists():
        load_dotenv(dotenv_path=DEFAULT_ENV_PATH)
    else:
        load_dotenv()

    raw = load_raw_config()

    # Normalize hours if needed (support legacy day->range dict)
    if "hours" in raw:
        raw["hours"] = normalize_hours(raw["hours"])

    try:
        config = RootConfig(**raw)
        # Ensure calendar directory exists (creates parent if needed)
        config.calendar.ensure_parent()
        return config
    except Exception as e:
        # Fail fast with clear message
        raise RuntimeError(f"Configuration validation failed: {e}") from e


def load_env_variables() -> dict:
    """
    Loads required environment variables (e.g., OPENAI_API_KEY) into a plain dict.
    """
    if DEFAULT_ENV_PATH.exists():
        load_dotenv(dotenv_path=DEFAULT_ENV_PATH)
    else:
        load_dotenv()

    result = {
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", "").strip(),
    }
    if not result["OPENAI_API_KEY"]:
        raise RuntimeError("OPENAI_API_KEY not set in environment.")
    return result
