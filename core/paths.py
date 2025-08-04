# core/paths.py

import os
from pathlib import Path

# Base directory for all persistent data, overridable in tests
BASE_DATA_DIR = Path(os.getenv("DATA_DIR", "data"))

# Calendar .ics
CALENDAR_ICS_PATH = BASE_DATA_DIR / "calendar" / "appointments.ics"

# Usage JSON
USAGE_JSON_PATH = BASE_DATA_DIR / "usage" / "usage.json"

# Call/session JSON
CALLS_JSON_PATH = BASE_DATA_DIR / "calls" / "calls.json"

# Structured logging NDJSON file + archive dir
STRUCT_LOG_DIR     = BASE_DATA_DIR / "logs"
STRUCT_LOG_FILE    = STRUCT_LOG_DIR / "structured_calls.ndjson"
STRUCT_LOG_ARCHIVE = STRUCT_LOG_DIR / "archive"
