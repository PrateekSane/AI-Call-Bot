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
    Test that invoke_gpt fetches user info, constructs system prompt,
    calls get_openai_response, and parses JSON from the GPT reply.
    """
    # Mock the call manager
    call_manager = MagicMock()
    call_manager.get_session_by_id.return_value = SessionData(
        session_id="session123",
        conference_name="conference123",
        user_info=UserInformation(
            user_name="Alice",
            user_number="1234567890"
        )
    )
    call_manager.get_chat_history.return_value = [
        {"role": "user", "content": "Hello, GPT!"}
    ]

    # We'll also patch the generate_system_prompt function if it lives in backend.services.prompts
    with patch("backend.services.openai_utils.generate_system_prompt", return_value="system prompt"):
        # Mock the openai_client response to be valid JSON
        gpt_reply_dict = {"response_method": "voice", "response_content": "This is some TwilioResponse content"}
        mock_openai_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(refusal=None, content=json.dumps(gpt_reply_dict)))]
        )

        result = await invoke_gpt("Hello GPT!", "session123", call_manager)

        # Check we got the JSON as a dict
        assert result == gpt_reply_dict

    # Ensure call_manager usage
    call_manager.get_session_by_id.assert_called_once()
    call_manager.add_to_chat_history.assert_any_call("session123", "user", "Hello GPT!")
    call_manager.add_to_chat_history.assert_any_call("session123", "assistant", gpt_reply_dict)

    # No error logs
    mock_logger.error.assert_not_called()


@pytest.mark.asyncio
async def test_invoke_gpt_json_parse_error(mock_logger, mock_openai_client):
    """
    Test that invoke_gpt logs an error if the GPT response is not valid JSON.
    """
    call_manager = MagicMock()
    call_manager.get_session_by_id.return_value = SessionData(
        session_id="session123",
        conference_name="conference123",
        user_info=UserInformation(
            user_name="Alice",
            user_email="alice@example.com",
            user_phone="1234567890"
        )
    )
    call_manager.get_chat_history.return_value = []
    
    # Return non-JSON content
    mock_openai_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(refusal=None, content="Invalid JSON"))]
    )

    with patch("backend.services.openai_utils.generate_system_prompt", return_value="system prompt"):
        result = await invoke_gpt("Some text", "session123", call_manager)
        assert result == {}  # Because we failed to parse JSON

    mock_logger.error.assert_called_once()
    assert "Error parsing GPT response:" in mock_logger.error.call_args[0][0]
