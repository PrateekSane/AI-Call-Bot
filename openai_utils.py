import openai
import os
from dotenv import load_dotenv
from prompts import SYSTEM_PROMPT
from utils import logger

openai.api_key = os.getenv('OPENAI_API_KEY')


async def get_openai_response(transcript: str) -> str:
    """
    Given user transcript, call OpenAI Chat or Completions.
    Keep it simple here: one user message + system prompt.
    """
    try:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": transcript},
        ]
        response = await openai.ChatCompletion.acreate(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.8,
        )
        # Extract the assistant text response
        assistant_reply = response.choices[0].message["content"]
        return assistant_reply.strip()
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return "I encountered an error. Please hold."
