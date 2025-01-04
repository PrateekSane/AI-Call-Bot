import asyncio
import json
import os
from dotenv import load_dotenv

from backend.core.constants import CallInfo
from backend.core.call_manager import CallManager
from backend.core.models import UserInformation
from backend.services.openai_utils import invoke_gpt

load_dotenv('../env/.env')

async def simulate_conversation(test_case="spotify_double_charge"):
    """Simulate a conversation with the AI assistant"""
    
    # Load test cases
    test_cases_path = os.path.join(os.path.dirname(__file__), 'test_cases.json')
    with open(test_cases_path, 'r') as f:
        test_cases = json.load(f)
    
    # Get the specified test case
    case = test_cases[test_case]
    
    # Create a test session
    test_call_manager = CallManager()
    session_id = test_call_manager.create_new_session()
    
    # Set up user info from test case
    user_info = UserInformation(**case['user_info'])
    
    # Store user info in session
    test_call_manager.set_session_value(session_id, CallInfo.USER_INFO, user_info.model_dump())
    
    print("\nSimulated AI Assistant Chat")
    print(f"Using test case: {test_case}")
    print("Type 'exit' to end the conversation")
    print("--------------------------------")
    
    while True:
        # Get user input
        user_input = input("\nYou: ").strip()
        if user_input.lower() == 'exit':
            break
        
        if not user_input:
            continue
            
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