import pytest

from backend.services.prompts import generate_system_prompt
from backend.core.constants import UserInformationKeys

def test_generate_system_prompt_no_user_info():
    """
    If no user info is provided, function should raise ValueError.
    """
    with pytest.raises(ValueError, match="User information is required"):
        generate_system_prompt(None)

def test_generate_system_prompt_missing_key():
    """
    If any required key (except additional_info) is missing, function should raise KeyError.
    """
    # Let's omit the account_number to simulate missing info
    user_info_incomplete = {
        UserInformationKeys.USER_NAME.value: "Alice",
        UserInformationKeys.USER_EMAIL.value: "alice@example.com",
        UserInformationKeys.REASON_FOR_CALL.value: "Billing question",
        # UserInformationKeys.ACCOUNT_NUMBER.value: "12345",  # omitted
        # additional_info is optional
    }
    with pytest.raises(KeyError, match="Missing required user information: account_number"):
        generate_system_prompt(user_info_incomplete)

def test_generate_system_prompt_success():
    """
    Test that the prompt is correctly formed with all required keys present (no additional_info).
    """
    user_info = {
        UserInformationKeys.USER_NAME.value: "Bob",
        UserInformationKeys.USER_EMAIL.value: "bob@example.com",
        UserInformationKeys.REASON_FOR_CALL.value: "Technical support",
        UserInformationKeys.ACCOUNT_NUMBER.value: "98765",
        # additional_info is optional
    }
    prompt = generate_system_prompt(user_info)
    
    # Check that the prompt contains expected values
    assert "You are the Bob's helpful assistant" in prompt
    assert "bob@example.com" in prompt
    assert "Technical support" in prompt
    assert "98765" in prompt

    # Should NOT contain the "Additional Information" section
    assert "Additional Information:" not in prompt

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
