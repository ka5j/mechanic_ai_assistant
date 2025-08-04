# assistant/assistant.py

import openai
from utils.call_logger import log_interaction
from core.config_loader import load_env_variables

# Load environment variables from .env
config = load_env_variables()

# Set OpenAI API key securely
openai.api_key = config["OPENAI_API_KEY"]

# System message defines AI behavior
SYSTEM_PROMPT = """
You are a smart, strict, and professional AI receptionist for a mechanic shop.
Only answer questions related to services, prices, timing, appointment booking,
and car-related general info. If someone asks something off-topic, say:
"I'm only trained to assist with mechanic shop-related questions."

Be polite, fast, accurate, and never make up prices or services.
If the question is too complex or uncertain, say:
"I’ll connect you to a human right away."
"""

def test_ask_ai(user_input: str) -> str:
    """
    Fake AI logic for CLI demo/testing without OpenAI costs.
    """
    # Simulated intelligent reply for safe testing
    mock_response = f"[Test AI] You asked: '{user_input}'. Here's a simulated assistant reply."
    
    # Log the interaction like real usage
    log_interaction("ai_response_mock", {
        "input": user_input,
        "response": mock_response
    })

    return mock_response

def ask_ai(user_input: str) -> str:
    """
    Sends user input to OpenAI and returns AI response with safe fallback.
    """
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



