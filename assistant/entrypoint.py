# assistant/entrypoint.py

import time
from booking.booking import handle_booking
from assistant.assistant import run_assistant
from datetime import datetime
from utils.structured_logger import log_event

def print_menu(options: dict):
    print("\n🔧 Please select a service or action:")
    for key, val in options.items():
        print(f"{key}. {val['label']}")
    print("0. Exit")

def start_assistant(config, phone_number, call_id, session, io_adapter):
    # Greet the caller
    io_adapter.prompt(f"\n👋 Hello from {config.get('shop_name', 'the shop')}! How can I help today?")
    session.add_history("greeting", output_data="greeting sent")
    log_event(session.call_id, "greeting", output_data="greeting prompt displayed")

    while True:
        options = {
            "1": {"label": "Book an appointment", "type": "booking"},
            "2": {"label": "Ask a question", "type": "question"},
        }
        print_menu(options)
        selection = io_adapter.collect("Select option: ")
        session.add_history("menu_selection", input_data=selection)
        log_event(session.call_id, "menu_selection", input_data=selection)

        if selection == "0":
            io_adapter.confirm("Goodbye!")
            session.add_history("exit", output_data="user exited")
            log_event(session.call_id, "exit", output_data="user exited")
            break

        action = options.get(selection, {}).get("type")
        if action == "booking":
            handle_booking(config, phone_number, call_id, session=session, io_adapter=io_adapter)
        elif action == "question":
            user_question = io_adapter.collect("What would you like to ask? ")
            if not user_question:
                io_adapter.prompt("No question entered.")
                continue
            session.add_history("user_question", input_data=user_question)
            log_event(session.call_id, "user_question", input_data=user_question)
            response = run_assistant(user_question, config, session=session)
            io_adapter.prompt(f"\n{response}")
            session.add_history("assistant_response", output_data=response)
            log_event(session.call_id, "assistant_response", output_data=response)
        else:
            io_adapter.prompt("This action type is not yet supported.")
            session.add_history("unsupported_action", input_data=selection)
            log_event(session.call_id, "unsupported_action", input_data=selection)
