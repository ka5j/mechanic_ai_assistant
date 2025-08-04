# cli/cli_router.py

import time
from datetime import datetime
from assistant.assistant import ask_ai
from core.booking_handler import handle_booking_flow
from utils.call_logger import log_interaction

def simulate_cli_call():
    """
    Simulate the full call experience through CLI.
    """
    print("📞 Welcome to the Mechanic Shop AI Assistant!")

    phone_number = input("Enter your phone number to start the call: ").strip()
    call_start = datetime.now()

    print("\n🤖 Hello! I'm your AI assistant.\n")
    print("Press:")
    print("1 - Book an appointment")
    print("2 - Ask a question")
    print("3 - Get service hours")
    print("4 - Exit")

    while True:
        choice = input("Your choice: ").strip()

        if choice == "1":
            handle_booking_flow()

        elif choice == "2":
            question = input("Ask your question: ").strip()
            reply = ask_ai(question)
            print(f"🤖 {reply}")

        elif choice == "3":
            print("🕒 We're open from 9:00 AM to 6:00 PM, Monday to Saturday.")

        elif choice == "4":
            break

        else:
            print("❌ Invalid choice. Please press 1, 2, 3 or 4.")

        print("\n---\n")
        print("Anything else? (press 1/2/3 or 4 to end)\n")

    call_end = datetime.now()
    duration_seconds = (call_end - call_start).seconds

    # Log metadata
    log_interaction("call_metadata", {
        "phone_number": phone_number,
        "call_start": str(call_start),
        "call_end": str(call_end),
        "duration_seconds": duration_seconds
    })

    print("📴 Call ended. Thank you for calling the mechanic shop!")

if __name__ == "__main__":
    simulate_cli_call()
