# core/config_loader.py

import json
import os
from dotenv import load_dotenv

REQUIRED_FIELDS = [
    "shop_name", "phone", "address", "hours", "services",
    "faq", "booking_slots", "reminders", "support_escalation", "calendar"
]

def load_env_variables():
    """
    Loads .env file securely from secrets folder.
    """
    dotenv_path = os.path.join(os.path.dirname(__file__), '..', 'secrets', '.env')
    load_dotenv(dotenv_path)

    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

    if not api_key:
        raise ValueError("❌ Missing OPENAI_API_KEY in .env file.")

    return {
        "OPENAI_API_KEY": api_key,
        "OPENAI_MODEL": model
    }

def load_config(path="config/demo_config.json"):
    """
    Loads assistant behavior configuration (shop info, booking, etc).
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"❌ Config file not found at: {path}")
    
    with open(path, "r") as f:
        config = json.load(f)

    # Validate structure
    for field in REQUIRED_FIELDS:
        if field not in config:
            raise ValueError(f"❌ Missing required config field: '{field}'")

    # Validate booking slots
    if "start" not in config["booking_slots"] or "end" not in config["booking_slots"]:
        raise ValueError("❌ 'booking_slots' must include both 'start' and 'end'.")

    # Validate calendar path
    if "ics_path" not in config["calendar"]:
        raise ValueError("❌ 'calendar' must include 'ics_path'.")

    print("✅ Config loaded successfully.")
    return config
