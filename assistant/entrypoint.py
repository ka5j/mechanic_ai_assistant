import time
from booking.booking import handle_booking
from utils.call_logger import log_interaction
from assistant.assistant import ask_ai

import sys
import time
from assistant.assistant import ask_ai
from datetime import datetime

def debug_cli_mode():
    """
    Debug mode: test the AI assistant in CLI by typing messages.
    Everything is logged and responses printed.
    """
    session_id = f"debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    log_interaction("debug_start", {"session_id": session_id, "start_time": time.ctime()})

    print("\n🚗 Mechanic AI Assistant (DEBUG MODE)")
    print("Type your questions below. Type 'exit' to quit.\n")

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in {"exit", "quit"}:
            log_interaction("debug_end", {"session_id": session_id, "end_time": time.ctime()})
            print("👋 Ending session. Goodbye!")
            break

        if not user_input:
            continue

        log_interaction("user_input", {"session_id": session_id, "input": user_input})
        ai_reply = ask_ai(user_input)
        print(f"Assistant: {ai_reply}\n")
        time.sleep(0.5)

def print_menu(options: dict):
    print("\n🔧 Please select a service:")
    for key, val in options.items():
        print(f"{key}. {val['label']}")
    print("0. Exit")

def get_user_selection(options: dict):
    while True:
        choice = input("👉 Enter your choice: ").strip()
        if choice == "0":
            return "exit"
        if choice in options:
            return choice
        print("❌ Invalid option. Please try again.")

def start_assistant(config, phone_number, call_id):
    print(f"\n🤖 {config['greeting']}")
    
    menu_options = config.get("menu", {})
    if not menu_options:
        print("❗ No options configured.")
        return

    while True:
        print_menu(menu_options)
        user_choice = get_user_selection(menu_options)

        if user_choice == "exit":
            print("👋 Thank you! Have a great day.")
            break

        selected_action = menu_options[user_choice]
        action_type = selected_action.get("type")
        action_prompt = selected_action.get("prompt")

        log_interaction(call_id, {
            "action": action_type,
            "menu_choice": selected_action['label'],
            "timestamp": time.time()
        })

        if action_type == "booking":
            handle_booking(call_id, phone_number)
        elif action_type == "question":
            response = ask_ai(action_prompt)
            print(f"\n🤖 {response}")
        else:
            print("⚠️ This action type is not yet supported.")
