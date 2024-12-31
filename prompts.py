from typing import Dict, Any
from constants import SYSTEM_PROMPT_TEMPLATE, SystemPromptKeys, DEFAULT_SYSTEM_INFO

def generate_system_prompt(system_info: Dict[str, Any] = None) -> str:
    """Generate system prompt based on provided information"""
    if system_info is None:
        system_info = DEFAULT_SYSTEM_INFO
    
    # Ensure all required keys exist with defaults if missing
    for key in SystemPromptKeys:
        if key.value not in system_info:
            system_info[key.value] = DEFAULT_SYSTEM_INFO[key.value]
    
    # Format additional info if present
    additional_info_str = ""
    if system_info.get(SystemPromptKeys.ADDITIONAL_INFO.value):
        additional_info_str = "\nAdditional Information:"
        for key, value in system_info[SystemPromptKeys.ADDITIONAL_INFO.value].items():
            additional_info_str += f"\n{key}: {value}"
    
    return SYSTEM_PROMPT_TEMPLATE.format(
        user_name=system_info[SystemPromptKeys.USER_NAME.value],
        user_email=system_info[SystemPromptKeys.USER_EMAIL.value],
        reason_for_call=system_info[SystemPromptKeys.REASON_FOR_CALL.value],
        account_number=system_info[SystemPromptKeys.ACCOUNT_NUMBER.value],
        additional_info=additional_info_str
    )