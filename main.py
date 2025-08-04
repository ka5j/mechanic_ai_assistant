# main.py

import sys
from core.config_loader import load_config
from utils.call_logger import log_call_start, log_call_end
from assistant.entrypoint import start_assistant
from assistant.session import CallSession
from assistant.io_adapter import CLIAdapter

def get_phone_number():
    while True:
        phone = input("📱 Enter customer's phone number (e.g., +1-647-555-1234): ").strip()
        if phone.startswith("+") and len(phone) >= 10:
            return phone
        print("❌ Invalid phone number. Please enter again.")

def main():
    print("\n🚗 Superior Auto Clinic – AI Receptionist\n")
    config = load_config()
    phone_number = get_phone_number()
    call_id, _ = log_call_start(phone_number)

    # NEW: create session and IO adapter
    session = CallSession(call_id=call_id, caller_number=phone_number, mode="customer")
    io = CLIAdapter()

    try:
        start_assistant(config, phone_number, call_id, session=session, io_adapter=io)
    except KeyboardInterrupt:
        print("\n🔌 Call interrupted manually.")
    except Exception as e:
        print(f"❗ An error occurred: {e}")

    log_call_end(call_id)
    print("📞 Call session ended.\n")

if __name__ == "__main__":
    main()
