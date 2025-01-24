from typing import Dict, Any

from backend.core.constants import UserInformationKeys


SYSTEM_PROMPT_TEMPLATE = """You are the {user_name}'s helpful assistant and you are calling on their behalf to a customer service agent. YOU ARE NOT {user_name}.
You are given the following pieces of information about {user_name}. Use this information to help the customer service agent. 
Keep your responses concise and to the point.

User Name: {user_name}
User Email: {user_email}
Reason for call: {reason_for_call}
Account Number: {account_number}
{additional_info}

You need to give the customer service agent the best possible information about the user so that they can help them. 
Return "call_back" when you don't have enough information to answer the question. 
Return "phone_tree" when you need to type information directly into the dial tree.
Return "voice" when youre responding or answering any questions.
Only Return "noop" only when you are either on hold or told to wait.

Return the response in the following format:
Do not make up information."""


def generate_system_prompt(user_info: Dict[str, Any] = None) -> str:
    """Generate system prompt based on provided information"""
    if not user_info:
        raise ValueError("User information is required")
    
    print(user_info)
    # Ensure all required keys exist with defaults if missing
    for key in UserInformationKeys:
        if key.value not in user_info and key.value != UserInformationKeys.ADDITIONAL_INFO:
            raise KeyError(f"Missing required user information: {key}")
    
    # Format additional info if present
    additional_info_str = ""
    if user_info.get(UserInformationKeys.ADDITIONAL_INFO.value):
        additional_info_str = "\nAdditional Information:"
        for key, value in user_info[UserInformationKeys.ADDITIONAL_INFO.value].items():
            additional_info_str += f"\n{key}: {value}"
    
    return SYSTEM_PROMPT_TEMPLATE.format(
        user_name=user_info[UserInformationKeys.USER_NAME.value],
        user_email=user_info[UserInformationKeys.USER_EMAIL.value],
        reason_for_call=user_info[UserInformationKeys.REASON_FOR_CALL.value],
        account_number=user_info[UserInformationKeys.ACCOUNT_NUMBER.value],
        additional_info=additional_info_str
    )