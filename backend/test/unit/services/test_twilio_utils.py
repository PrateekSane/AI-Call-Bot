import pytest
from unittest.mock import MagicMock, patch
from twilio.twiml.voice_response import VoiceResponse

from backend.services.twilio_utils import (
    create_call,
    create_conference,
    is_redirect,
    end_call
)


@pytest.fixture
def mock_twilio_client():
    """
    Provide a mocked Twilio client fixture for tests.
    """
    return MagicMock()


def test_create_call(mock_twilio_client):
    """
    Test that create_call constructs the call with the correct parameters
    and returns the call object.
    """
    # Setup: define fake arguments
    to = "+15558675309"
    from_ = "+13335557777"
    url = "http://example.com/voice"
    status_callback = "http://example.com/status"

    # Create a fake call object
    fake_call = MagicMock()
    mock_twilio_client.calls.create.return_value = fake_call

    result = create_call(
        twilio_client=mock_twilio_client,
        to=to,
        from_=from_,
        url=url,
        status_callback=status_callback,
    )

    # Assert call to Twilio's create method
    mock_twilio_client.calls.create.assert_called_once_with(
        to=to,
        from_=from_,
        url=url,
        status_callback=status_callback,
        status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
        status_callback_method='POST'
    )

    # Assert we got the mock object returned
    assert result == fake_call


def test_create_call_with_status_callback_event(mock_twilio_client):
    """
    Test create_call when a custom status_callback_event is provided.
    """
    custom_events = ["initiated", "answered"]
    create_call(
        twilio_client=mock_twilio_client,
        to="+15551234567",
        from_="+15557654321",
        url="http://test.com/voice",
        status_callback="http://test.com/status",
        status_callback_event=custom_events,
        status_callback_method="GET"
    )
    mock_twilio_client.calls.create.assert_called_once_with(
        to="+15551234567",
        from_="+15557654321",
        url="http://test.com/voice",
        status_callback="http://test.com/status",
        status_callback_event=custom_events,
        status_callback_method="GET"
    )


def test_create_conference():
    """
    Test that create_conference returns a Dial with the correct conference settings.
    """
    conference_name = "TestConference"
    call_events_url = "http://example.com/events"

    dial = create_conference(
        conference_name=conference_name,
        call_events_url=call_events_url
    )

    # Convert Dial object to TwiML string
    twiml_str = str(dial)
    # The <Dial> tag should contain a <Conference> with the correct attributes
    assert f"statusCallback=\"{call_events_url}\"" in twiml_str
    assert f"startConferenceOnEnter=\"true\"" in twiml_str
    assert f"endConferenceOnExit=\"false\"" in twiml_str
    assert 'statusCallbackEvent="join leave"' in twiml_str



def test_create_conference_with_custom_params():
    """
    Test create_conference with custom status_callback_event, method, 
    start_conference_on_enter, end_conference_on_exit.
    """
    dial = create_conference(
        conference_name="CustomConf",
        call_events_url="http://test-status.com",
        status_callback_event=["join", "leave", "mute"],
        status_callback_method="GET",
        start_conference_on_enter=False,
        end_conference_on_exit=True
    )
    twiml_str = str(dial)
    assert "<Conference" in twiml_str
    assert "statusCallbackEvent=\"join leave mute\"" in twiml_str
    assert "statusCallbackMethod=\"GET\"" in twiml_str
    assert "startConferenceOnEnter=\"false\"" in twiml_str
    assert "endConferenceOnExit=\"true\"" in twiml_str


@pytest.mark.parametrize("transcript,expected", [
    ("Redirect me please", True),
    ("redirect now", True),
    ("some random words", False),
    ("some ReDiRect words", True),  # check case-insensitivity
    ("", False),
])
def test_is_redirect(transcript, expected, capsys):
    """
    Test is_redirect behavior for various transcripts, also confirm the print output.
    """
    result = is_redirect(transcript)
    assert result == expected
    captured = capsys.readouterr()
    # The function prints "Is redirect: <True/False>"
    assert f"Is redirect: {expected}" in captured.out


def test_end_call(mock_twilio_client):
    """
    Test that end_call correctly updates a call's status to 'completed'.
    """
    call_sid = "CA12345"
    end_call(mock_twilio_client, call_sid)
    mock_twilio_client.calls.assert_called_once_with(call_sid)
    mock_twilio_client.calls(call_sid).update.assert_called_once_with(status="completed")
