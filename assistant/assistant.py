# assistant/assistant.py

import openai
from utils.call_logger import log_interaction
from core.config_loader import load_env_variables

# Load environment variables
config = load_env_variables()
openai.api_key = config["OPENAI_API_KEY"]

# Static system prompt
SYSTEM_PROMPT = """
You are a strict, polite, and highly efficient AI receptionist for a mechanic shop.
Only answer questions about the shop’s services, pricing, hours, bookings, and car-related help.
If something is outside your scope, respond with:
"I'm only trained to assist with mechanic shop-related questions."

Always be helpful and accurate, and if you're unsure, escalate.
"""

def get_faq_response(user_input: str, full_config: dict) -> str | None:
    """
    Returns an exact match FAQ response if found, else None.
    """
    for question, answer in full_config.get("faq", {}).items():
        if user_input.lower().strip() == question.lower().strip():
            return answer
    return None

def get_service_response(user_input: str, full_config: dict) -> str | None:
    """
    Returns details about a known service if found in user input.
    """
    services = full_config.get("services", [])
    for service in services:
        if service["name"].lower() in user_input.lower():
            return (
                f"🔧 {service['name']}:\n"
                f"{service['description']}\n"
                f"💵 Price: {service['price']}\n"
                f"⏱ Duration: {service['duration_minutes']} minutes"
            )
    return None

def run_assistant(user_input: str, full_config: dict) -> str:
    """
    Full assistant logic with dynamic FAQ/service lookup before using OpenAI.
    """
    # First: Check for direct FAQ match
    faq_response = get_faq_response(user_input, full_config)
    if faq_response:
        log_interaction("faq_match", {"input": user_input, "response": faq_response})
        return faq_response

    # Second: Check if question mentions any known service
    service_response = get_service_response(user_input, full_config)
    if service_response:
        log_interaction("service_match", {"input": user_input, "response": service_response})
        return service_response

    # Otherwise: Use OpenAI for natural AI response
    try:
        response = openai.ChatCompletion.create(
            model=config["OPENAI_MODEL"],
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_input}
            ],
            temperature=0.3,
            max_tokens=350
        )
        reply = response['choices'][0]['message']['content'].strip()
        log_interaction("ai_response", {"input": user_input, "response": reply})
        return reply

    except Exception as e:
        error_message = f"⚠️ Assistant error: {str(e)}"
        log_interaction("error", {"input": user_input, "error": str(e)})
        return error_message
