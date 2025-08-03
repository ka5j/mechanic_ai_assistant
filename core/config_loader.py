import json
import os

REQUIRED_FIELDS = [
    "shop_name", "phone", "address", "hours", "services",
    "faq", "booking_slots", "reminders", "support_escalation", "calendar"
]

def load_config(path="config/demo_config.json"):
    if not os.path.exists(path):
        raise FileNotFoundError(f"❌ Config file not found at: {path}")
    
    with open(path, "r") as f:
        config = json.load(f)
    
    # Validate required fields
    for field in REQUIRED_FIELDS:
        if field not in config:
            raise ValueError(f"❌ Missing required config field: {field}")

    # Validate time ranges
    if "start" not in config["booking_slots"] or "end" not in config["booking_slots"]:
        raise ValueError("❌ booking_slots must include 'start' and 'end' time.")
    
    if "ics_path" not in config["calendar"]:
        raise ValueError("❌ calendar must include 'ics_path' to save .ics files.")

    print("✅ Config loaded successfully.")
    return config
