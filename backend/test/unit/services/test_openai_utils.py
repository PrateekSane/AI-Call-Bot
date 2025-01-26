import pytest
import os
import json
from unittest.mock import patch, MagicMock
from backend.models.models import UserInformation
from backend.models.session_data import SessionData

from backend.services.openai_utils import (
    get_openai_response,
    invoke_gpt
)


@pytest.fixture
def mock_logger():
    """
    Patch the logger inside openai_utils so we can assert calls.
    """
    with patch("backend.services.openai_utils.logger") as mock_log:
        yield mock_log


@pytest.fixture
def mock_openai_client():
    """
    Patch the OpenAI client so we don't make real API calls.
    """
    with patch("backend.services.openai_utils.openai_client") as mock_client:
        yield mock_client


def test_get_openai_response_success(mock_logger, mock_openai_client):
    """
    Test a successful call to get_openai_response.
    """
    # Mock the response object from openai_client
    mock_choice = MagicMock()
    mock_choice.message = MagicMock()
    mock_choice.message.refusal = None  # no refusal
    mock_choice.message.content = "Test GPT content"

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_openai_client.chat.completions.create.return_value = mock_response

    result = get_openai_response("system prompt", "hello user")
    assert result == "Test GPT content"
    # Ensure no error log
    mock_logger.error.assert_not_called()

    # Check that the correct arguments were passed to create(...)
    mock_openai_client.chat.completions.create.assert_called_once()
    create_args, create_kwargs = mock_openai_client.chat.completions.create.call_args
    assert create_kwargs["model"] == "gpt-4o-mini"
    assert create_kwargs["messages"][0]["role"] == "system"
    assert create_kwargs["messages"][0]["content"] == "system prompt"
    assert create_kwargs["messages"][1]["role"] == "user"
    assert create_kwargs["messages"][1]["content"] == "hello user"


def test_get_openai_response_refusal(mock_logger, mock_openai_client):
    """
    Test the scenario where the assistant replies with a refusal.
    """
    mock_choice = MagicMock()
    mock_choice.message = MagicMock()
    mock_choice.message.refusal = "I refuse to comply."  # simulate refusal
    mock_choice.message.content = "Some content"

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_openai_client.chat.completions.create.return_value = mock_response

    result = get_openai_response("system prompt", "hello user")
    # The code prints the refusal and returns an empty string
    assert result == ""
    mock_logger.error.assert_not_called()  # no error, just a refusal message


def test_get_openai_response_exception(mock_logger, mock_openai_client):
    """
    Test error handling if an exception is raised.
    """
    mock_openai_client.chat.completions.create.side_effect = Exception("OpenAI call failed")

    result = get_openai_response("system prompt", "hello user")
    assert result == "I encountered an error. Please hold."
    mock_logger.error.assert_called_once()
    assert "OpenAI error: OpenAI call failed" in mock_logger.error.call_args[0][0]


@pytest.mark.asyncio
async def test_invoke_gpt_success(mock_logger, mock_openai_client):
    """
    Test that invoke_gpt fetches user info, constructs a system prompt,
    calls get_openai_response, and parses JSON from the GPT reply.
    Also confirm that session_data.add_to_chat_history is used (i.e.,
    the chat history is appended to the SessionData object).
    """

    # 1. Create a SessionData object with empty or initial chat_history:
    session_data = SessionData(
        session_id="session123",
        conference_name="conference123",
        user_info=UserInformation(
            user_name="Alice",
            user_email="alice@example.com",
            account_number="1234567890",
            reason_for_call="I need help with my account"
        ),
    )

    # 2. Mock the call_manager so that get_session_by_id returns our session_data
    call_manager = MagicMock()
    call_manager.get_session_by_id.return_value = session_data

    # 3. Mock generate_system_prompt if needed
    with patch("backend.services.openai_utils.generate_system_prompt", return_value="system prompt"):
        # 4. Mock the openai_client response to be valid JSON
        gpt_reply_dict = {"response_method": "voice", "response_content": "This is some TwilioResponse content"}
        mock_openai_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(refusal=None, content=json.dumps(gpt_reply_dict)))]
        )

        # 5. Invoke the function under test
        result = await invoke_gpt("Hello GPT!", "session123", call_manager)
        assert result == gpt_reply_dict

    # 6. We expect session_data.add_to_chat_history to have appended two entries:
    #    - The user prompt ("Hello GPT!")
    #    - The GPT response (gpt_reply_dict)

    # Verify call_manager usage
    call_manager.get_session_by_id.assert_called_once_with("session123")
    
    # Now check that the session_data’s chat_history was updated
    assert len(session_data.chat_history) == 2

    assert session_data.chat_history[0].role == "user"
    assert session_data.chat_history[0].content == "Hello GPT!"

    assert session_data.chat_history[1].role == "assistant"
    assert session_data.chat_history[1].content == json.dumps(gpt_reply_dict)

    # Finally, ensure no error logs
    mock_logger.error.assert_not_called()


@pytest.mark.asyncio
async def test_invoke_gpt_json_parse_error(mock_logger, mock_openai_client):
    """
    Test that invoke_gpt logs an error if the GPT response is not valid JSON.
    """
    # Create a SessionData object with valid UserInformation
    session_data = SessionData(
        session_id="session123",
        conference_name="conference123",
        user_info=UserInformation(
            user_name="Alice",
            user_email="alice@example.com",
            account_number="1234567890",
            reason_for_call="I need help with my account"
        ),
    )

    call_manager = MagicMock()
    call_manager.get_session_by_id.return_value = session_data

    # Return non-JSON content from the mocked OpenAI call
    mock_openai_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(refusal=None, content="Invalid JSON"))]
    )

    with patch("backend.services.openai_utils.generate_system_prompt", return_value="system prompt"):
        result = await invoke_gpt("Some text", "session123", call_manager)
        # Because we failed to parse JSON, we expect an empty dict
        assert result == {}

    # Confirm we logged an error
    mock_logger.error.assert_called_once()
    assert "Error parsing GPT response:" in mock_logger.error.call_args[0][0]
