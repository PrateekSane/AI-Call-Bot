import pytest

from backend.services.prompts import generate_system_prompt
from backend.core.constants import UserInformationKeys

def test_generate_system_prompt_no_user_info():
    """
    If no user info is provided, function should raise ValueError.
    """
    with pytest.raises(ValueError, match="User information is required"):
        generate_system_prompt(None)

def test_generate_system_prompt_with_additional_info():
    """
    If additional_info is present, it should be included in the prompt.
    """
    user_info = {
        UserInformationKeys.USER_NAME.value: "Carol",
        UserInformationKeys.USER_EMAIL.value: "carol@example.com",
        UserInformationKeys.REASON_FOR_CALL.value: "Billing inquiry",
        UserInformationKeys.ACCOUNT_NUMBER.value: "12345",
        UserInformationKeys.ADDITIONAL_INFO.value: {
            "address": "123 Main St",
            "preferred_contact_time": "Morning",
        },
    }
    prompt = generate_system_prompt(user_info)
    
    # Verify the main info
    assert "Carol" in prompt
    assert "carol@example.com" in prompt
    assert "Billing inquiry" in prompt
    assert "12345" in prompt

    # Verify additional info section
    assert "Additional Information:" in prompt
    assert "address: 123 Main St" in prompt
    assert "preferred_contact_time: Morning" in prompt
