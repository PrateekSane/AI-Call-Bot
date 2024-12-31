from typing import Dict, Any

from backend.core.constants import UserInformationKeys, SYSTEM_PROMPT_TEMPLATE


def generate_system_prompt(user_info: Dict[str, Any] = None) -> str:
    """Generate system prompt based on provided information"""
    if not user_info:
        raise ValueError("User information is required")
    
    # Ensure all required keys exist with defaults if missing
    for key in UserInformationKeys:
        if key.value not in user_info and key.value != UserInformationKeys.ADDITIONAL_INFO.value:
            raise KeyError(f"Missing required user information: {key.value}")
    
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