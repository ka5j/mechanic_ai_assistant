import time
import datetime
from core.config_loader import load_config
from utils.call_logger import log_call_start, log_call_end
from assistant.entrypoint import start_assistant

def get_phone_number():
    while True:
        phone = input("📱 Enter customer's phone number (e.g., +1-647-555-1234): ").strip()
        if phone.startswith("+") and len(phone) >= 10:
            return phone
        print("❌ Invalid phone number. Please enter again.")

def main():
    print("🚗 Superior Auto Clinic – AI Receptionist\n")
    
    # Load config
    config = load_config()

    # Get phone number & log call
    phone_number = get_phone_number()
    call_id, call_start_time = log_call_start(phone_number)
    
    # Start assistant conversation
    try:
        start_assistant(config, phone_number, call_id)
    except KeyboardInterrupt:
        print("\n🔌 Call interrupted manually.")
    except Exception as e:
        print(f"❗ An error occurred: {e}")
    
    # Log end of call
    log_call_end(call_id)

if __name__ == "__main__":
    main()
