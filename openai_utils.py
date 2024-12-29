from openai import OpenAI
import os
from dotenv import load_dotenv
from prompts import SYSTEM_PROMPT
from utils import logger

openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def get_openai_response(transcript: str) -> str:
    """
    Given user transcript, call OpenAI Chat or Completions.
    Keep it simple here: one user message + system prompt.
    """
    try:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
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
