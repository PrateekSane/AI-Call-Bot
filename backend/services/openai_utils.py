from openai import OpenAI
import os
from utils import logger

openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def get_openai_response(system_prompt: str, transcript: str) -> str:
    """Simple OpenAI chat completion with system prompt and user transcript"""
    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": transcript},
        ]
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
        )

        assistant_reply = response.choices[0].message.content.strip()
        return assistant_reply
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return "I encountered an error. Please hold."
