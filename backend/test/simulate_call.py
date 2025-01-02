import asyncio
from typing import Optional
import os
from dotenv import load_dotenv

from backend.core.constants import CallInfo
from backend.core.call_manager import CallManager
from backend.core.models import UserInformation
from backend.services.openai_utils import invoke_gpt

load_dotenv('../env/.env')

async def simulate_conversation():
    """Simulate a conversation with the AI assistant"""
    
    # Create a test session
    test_call_manager = CallManager()
    session_id = test_call_manager.create_new_session()
    
    # Set up test user info
    user_info = UserInformation(
        user_name="Test User",
        user_email="test@example.com",
        reason_for_call="Testing the system",
        account_number="12345",
        additional_info={"test_mode": "true"}
    )
    
    # Store user info in session
    test_call_manager.set_session_value(session_id, CallInfo.USER_INFO, user_info.model_dump())
    
    # Mark session as ready
    test_call_manager.set_stream_ready(session_id, True)
    
    print("\nSimulated AI Assistant Chat")
    print("Type 'exit' to end the conversation")
    print("--------------------------------")
    
    while True:
        # Get user input
        user_input = input("\nYou: ").strip()
        if user_input.lower() == 'exit':
            break
            
        # Process the input through GPT
        ai_response = await invoke_gpt(
            transcript=user_input,
            session_id=session_id,
            call_manager=test_call_manager
        )
        print(f"\nAssistant: {ai_response}")
    
    # Clean up
    test_call_manager.delete_session(session_id)
    print("\nConversation ended")

if __name__ == "__main__":
    asyncio.run(simulate_conversation()) 