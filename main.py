import sys
import time
import datetime

from core.config_loader import load_config
from utils.call_logger import log_call_start, log_call_end
from assistant.entrypoint import start_assistant, debug_cli_mode


def get_phone_number():
    while True:
        phone = input("📱 Enter customer's phone number (e.g., +1-647-555-1234): ").strip()
        if phone.startswith("+") and len(phone) >= 10:
            return phone
        print("❌ Invalid phone number. Please enter again.")


def main():
    print("🧠 Welcome to Mechanic AI Assistant Backend")
    print("Select mode:")
    print("1. Debug CLI Mode (Safe Testing)")
    print("2. Full AI Assistant Simulation")
    print("3. Exit")

    choice = input("Enter option (1/2/3): ").strip()

    if choice == "1":
        debug_cli_mode()

    elif choice == "2":
        print("\n🚗 Superior Auto Clinic – AI Receptionist\n")
        config = load_config()
        phone_number = get_phone_number()
        call_id, call_start_time = log_call_start(phone_number)

        try:
            start_assistant(config, phone_number, call_id)
        except KeyboardInterrupt:
            print("\n🔌 Call interrupted manually.")
        except Exception as e:
            print(f"❗ An error occurred: {e}")

        log_call_end(call_id)

    elif choice == "3":
        print("Goodbye!")
        sys.exit(0)

    else:
        print("❌ Invalid option. Try again.")


if __name__ == "__main__":
    main()
