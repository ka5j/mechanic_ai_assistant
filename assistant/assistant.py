# assistant/assistant.py

import openai
from utils.call_logger import log_interaction
from core.config_loader import load_env_variables

from openai import OpenAI
from utils.usage_guard import can_call_model, record_usage

# Load environment variables
config = load_env_variables()
client = OpenAI(api_key=config["OPENAI_API_KEY"])

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

def run_assistant(user_input: str, full_config: dict = None) -> str:
    # Optional: dynamic FAQ/service logic if you merged that version
    # (skip here if using simpler version)
    if full_config:
        from assistant.assistant import get_faq_response, get_service_response
        faq_resp = get_faq_response(user_input, full_config)
        if faq_resp:
            log_interaction("faq_match", {"input": user_input, "response": faq_resp})
            return faq_resp
        svc_resp = get_service_response(user_input, full_config)
        if svc_resp:
            log_interaction("service_match", {"input": user_input, "response": svc_resp})
            return svc_resp

    # Budget guard
    estimated_prompt_tokens = len(user_input.split())  # rough proxy
    if not can_call_model(estimated_prompt_tokens):
        msg = "⚠️ Budget limit reached. Cannot process further requests right now."
        log_interaction("usage_blocked", {"input": user_input, "reason": "budget_exceeded"})
        return msg

    try:
        response = client.chat.completions.create(
            model=config["OPENAI_MODEL"],
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_input}
            ],
            temperature=0.3,
            max_tokens=300
        )

        # Record actual usage if available
        usage_info = response.usage if hasattr(response, "usage") else None
        if usage_info:
            prompt_tokens = usage_info.get("prompt_tokens", 0)
            completion_tokens = usage_info.get("completion_tokens", 0)
            total = prompt_tokens + completion_tokens
            record_usage(total)
        else:
            # fallback: estimate from response length
            reply_text = response.choices[0].message.content.strip()
            estimated_tokens = len(reply_text.split())
            record_usage(estimated_tokens)

        reply = response.choices[0].message.content.strip()
        log_interaction("ai_response", {"input": user_input, "response": reply})
        return reply

    except Exception as e:
        error_message = f"⚠️ Assistant error: {str(e)}"
        log_interaction("error", {"input": user_input, "error": str(e)})
        return error_message
