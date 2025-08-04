# assistant/entrypoint.py

import time
from booking.booking import handle_booking
from utils.call_logger import log_interaction
from assistant.assistant import run_assistant
from datetime import datetime

def print_menu(options: dict):
    print("\n🔧 Please select a service or action:")
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
    """
    Runs the main assistant loop with menu-based options using real OpenAI and booking logic.
    """
    print(f"\n🤖 Welcome to {config.get('shop_name', 'the shop')}! How can I help you today?")
    
    # Build a minimal menu if none supplied
    menu_options = config.get("menu")
    if not menu_options:
        menu_options = {
            "1": {"label": "Book an appointment", "type": "booking"},
            "2": {"label": "Ask a question", "type": "question", "prompt": "General inquiry"}
        }

    while True:
        print_menu(menu_options)
        user_choice = get_user_selection(menu_options)

        if user_choice == "exit":
            print("👋 Thank you! Have a great day.")
            break

        selected_action = menu_options[user_choice]
        action_type = selected_action.get("type")
        action_prompt = selected_action.get("prompt", "")

        log_interaction(call_id, {
            "action": action_type,
            "menu_choice": selected_action.get("label"),
            "timestamp": time.time()
        })

        if action_type == "booking":
            handle_booking(config, phone_number, call_id)
        elif action_type == "question":
            user_question = input("🗣️ What would you like to ask? ").strip()
            if not user_question:
                print("❌ No question entered.")
                continue
            response = run_assistant(user_question, config)
            print(f"\n🤖 {response}")
        else:
            print("⚠️ This action type is not yet supported.")
