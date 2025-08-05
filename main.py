#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# 1) Auto-load your .env from the `secrets/` directory
from dotenv import load_dotenv
import os
import sys
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent.resolve()

# Path to your .env inside secrets/
DOTENV_PATH = PROJECT_ROOT / "secrets" / ".env"
if not DOTENV_PATH.exists():
    raise RuntimeError(f".env file not found at {DOTENV_PATH}")
# load into os.environ (override any existing vars)
load_dotenv(DOTENV_PATH, override=True)

# Ensure the key is present
if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError("OPENAI_API_KEY not set in secrets/.env")

# 2) Make project modules importable
sys.path.insert(0, str(PROJECT_ROOT))

# 3) Configure data directory
os.environ.setdefault("DATA_DIR", str(PROJECT_ROOT / "data"))

# 4) Core imports
from openai import OpenAI
from core.config_loader import load_env_variables, load_config
from utils.usage_guard import can_call_model, record_usage
from utils.structured_logger import log_event
from assistant.assistant import process_interaction
from assistant.session import CallSession
from io_adapters.console_adapter import ConsoleAdapter

def main():
    # Load environment & config
    env    = load_env_variables()
    client = OpenAI(api_key=env["OPENAI_API_KEY"])
    config = load_config()

    print("AI Receptionist CLI")
    print("Type 'exit' or Ctrl-D to quit.")
    print("─────────────────────────────────\n")

    while True:
        try:
            number = input(">>> New call! Enter customer phone number: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not number or number.lower() in ("exit", "quit"):
            print("Goodbye!")
            break

        session    = CallSession(number)
        io_adapter = ConsoleAdapter()

        print(f"\nHello! I’m your AI receptionist. How can I help you today?\n")

        while True:
            try:
                user_input = io_adapter.collect("> ")
            except (EOFError, KeyboardInterrupt):
                print("\nCall ended.")
                break

            if not user_input or user_input.lower() in ("bye", "hangup", "end call", "exit"):
                print("Call closed.\n")
                break

            try:
                process_interaction(user_input, session, io_adapter)
            except Exception as e:
                # Unexpected error → escalate
                io_adapter.prompt("Sorry, something went wrong. Transferring you to a human.")
                print(f"[ERROR] {e!r}")

        # back to “New call” loop

if __name__ == "__main__":
    main()
