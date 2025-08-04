# assistant/entrypoint.py

import time
from datetime import datetime
from booking.booking import handle_booking
from utils.call_logger import log_interaction
from assistant.assistant import run_assistant

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
            handle_booking(config, phone_number)
        elif action_type == "question":
            response = run_assistant(action_prompt)
            print(f"\n🤖 {response}")
        else:
            print("⚠️ This action type is not yet supported.")
