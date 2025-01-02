from openai import OpenAI
import os
from backend.utils.utils import logger
from typing import List, Dict

openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def get_openai_response(system_prompt: str, user_message: str, chat_history: List[Dict[str, str]] = None) -> str:
    """Get response from OpenAI API."""
    try:
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add chat history if provided
        if chat_history:
            messages.extend(chat_history)
        else:
            messages.append({"role": "user", "content": user_message})

        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.7,
            max_tokens=150
        )

        assistant_reply = response.choices[0].message.content.strip()
        return assistant_reply
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return "I encountered an error. Please hold."
