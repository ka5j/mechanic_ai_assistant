# core/config_loader.py

import json
from pathlib import Path
from dotenv import load_dotenv
import os
from core.config_schema import RootConfig

# Path constants (adjust if your layout differs)
DEFAULT_CONFIG_PATH = Path("config/demo_config.json")
DEFAULT_ENV_PATH = Path("secrets/.env")


def load_raw_config(path: Path = DEFAULT_CONFIG_PATH) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found at {path.resolve()}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_config() -> RootConfig:
    """
    Loads environment variables and the JSON config, validates against schema,
    and returns a typed RootConfig instance.
    """
    # Load .env early so any env overrides are present
    if DEFAULT_ENV_PATH.exists():
        load_dotenv(dotenv_path=DEFAULT_ENV_PATH)
    else:
        # Still attempt to load default env if user specified alternative via environment
        load_dotenv()

    raw = load_raw_config()
    try:
        config = RootConfig(**raw)
        # Ensure calendar directory exists (creates parent if needed)
        config.calendar.ensure_parent()
        return config
    except Exception as e:
        # Wrap with context for clarity
        raise RuntimeError(f"Configuration validation failed: {e}") from e


def load_env_variables() -> dict:
    """
    Loads required environment variables (e.g., OPENAI_API_KEY) into a plain dict.
    Does not validate beyond presence; caller can extend if needed.
    """
    # Ensure .env is loaded as well
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
