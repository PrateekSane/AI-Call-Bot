from openai import OpenAI
import os
from backend.utils.utils import logger
from typing import List, Dict
from backend.core.constants import CallInfo
from backend.services.prompts import generate_system_prompt
from backend.models.models import OpenAIResponseFormat
import json

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
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7,
            max_tokens=150,
            response_format={
                'type': 'json_schema',
                'json_schema': 
                    {
                        "name":"TwilioResponse", 
                        "schema": OpenAIResponseFormat.model_json_schema()
                    }
            } 
        )

        assistant_reply = response.choices[0].message
        if assistant_reply.refusal:
            # handle refusal
            print(assistant_reply.refusal)
            return "" 
        return assistant_reply.content.strip()

    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return "I encountered an error. Please hold."

async def invoke_gpt(transcript, session_id, call_manager) -> Dict:
    """Handle transcript from either websocket or test"""
    logger.info(f"[STT Transcript] {transcript}")

    # Get user info and generate prompt
    session_data = call_manager.get_session_by_id(session_id)
    user_info = session_data.get_user_info().model_dump()
    system_prompt = generate_system_prompt(user_info)
    # Add user message to history
    session_data.add_to_chat_history("user", transcript)
    
    # Get chat history
    chat_history = session_data.get_chat_history()
    
    # Get GPT response
    gpt_reply = get_openai_response(system_prompt, transcript, chat_history)
    try:
        session_data.add_to_chat_history("assistant", gpt_reply)

        gpt_reply_json = json.loads(gpt_reply)
        logger.info(f"[GPT Response] {gpt_reply_json}")
    except Exception as e:
        logger.error(f"Error parsing GPT response: {e}")
        gpt_reply = {}

    # Add assistant response to history
    return gpt_reply_json
