from typing import Dict, Any

from backend.core.constants import UserInformationKeys, SYSTEM_PROMPT_TEMPLATE


def generate_system_prompt(system_info: Dict[str, Any] = None) -> str:
    """Generate system prompt based on provided information"""
    if not system_info:
        raise ValueError("System information is required")
    
    # Ensure all required keys exist with defaults if missing
    for key in UserInformationKeys:
        if key.value not in system_info and key.value != UserInformationKeys.ADDITIONAL_INFO.value:
            raise KeyError(f"Missing required system information: {key.value}")
    
    # Format additional info if present
    additional_info_str = ""
    if system_info.get(UserInformationKeys.ADDITIONAL_INFO.value):
        additional_info_str = "\nAdditional Information:"
        for key, value in system_info[UserInformationKeys.ADDITIONAL_INFO.value].items():
            additional_info_str += f"\n{key}: {value}"
    
    return SYSTEM_PROMPT_TEMPLATE.format(
        user_name=system_info[UserInformationKeys.USER_NAME.value],
        user_email=system_info[UserInformationKeys.USER_EMAIL.value],
        reason_for_call=system_info[UserInformationKeys.REASON_FOR_CALL.value],
        account_number=system_info[UserInformationKeys.ACCOUNT_NUMBER.value],
        additional_info=additional_info_str
    )