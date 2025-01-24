import pytest
from datetime import datetime

from backend.models.models import UserInformation, ChatMessage, CallType, MetaCallSids

from backend.models.session_data import SessionData

# -------------------------------------------------------------------

@pytest.fixture
def session_data():
    """Provides a fresh SessionData object for testing."""
    return SessionData(session_id="test_session_id", conference_name="test_conference")


def test_constructor_defaults(session_data):
    """
    Test that the constructor sets required fields and defaults properly.
    """
    assert session_data.session_id == "test_session_id"
    assert session_data.conference_name == "test_conference"
    assert session_data.meta_call_sids is None, "Should default to None unless set."
    assert session_data.bot_number is None
    assert session_data.cs_number is None
    assert session_data.user_number is None
    assert session_data.user_info is None
    assert session_data.ready_for_stream is False
    assert session_data.call_sids is not None, "call_sids should be initialized by default."
    assert session_data.chat_history == [], "chat_history should start empty."
    
    # Check that time_created is near 'now'
    assert isinstance(session_data.time_created, datetime)
    assert abs((datetime.now() - session_data.time_created).total_seconds()) < 5, \
        "time_created should be within a reasonable range."


def test_set_and_get_bot_number(session_data):
    """
    Test bot_number setter and getter.
    """
    test_bot_number = "+15550001111"
    session_data.set_bot_number(test_bot_number)
    assert session_data.get_bot_number() == test_bot_number


def test_set_and_get_cs_number(session_data):
    """
    Test customer service number setter and getter.
    """
    test_cs_number = "+16660002222"
    session_data.set_cs_number(test_cs_number)
    assert session_data.get_cs_number() == test_cs_number


def test_set_and_get_user_number(session_data):
    """
    Test user number setter and getter.
    """
    test_user_number = "+17770003333"
    session_data.set_user_number(test_user_number)
    assert session_data.get_user_number() == test_user_number


def test_set_and_get_user_info(session_data):
    """
    Test user info setter and getter.
    """
    user_info = UserInformation(user_name="user123", user_email="user123@example.com", reason_for_call="test", account_number="1234567890", additional_info={"key": "value"})
    session_data.set_user_info(user_info)
    returned_info = session_data.get_user_info()
    assert returned_info is not None
    assert returned_info.user_name == "user123"
    assert returned_info.user_email == "user123@example.com"
    assert returned_info.reason_for_call == "test"
    assert returned_info.account_number == "1234567890"
    assert returned_info.additional_info == {"key": "value"}


def test_call_sids_user(session_data):
    """
    Test set_call_sid and get_call_sid with a USER call.
    """
    call_sid = "user_call_sid"
    session_data.set_call_sid(CallType.USER, call_sid)
    assert session_data.get_call_sid(CallType.USER) == call_sid


def test_call_sids_customer_service(session_data):
    """
    Test set_call_sid and get_call_sid with a CUSTOMER_SERVICE call.
    """
    call_sid = "cs_call_sid"
    session_data.set_call_sid(CallType.CUSTOMER_SERVICE, call_sid)
    assert session_data.get_call_sid(CallType.CUSTOMER_SERVICE) == call_sid


def test_call_sids_bot_requires_is_outbound(session_data):
    """
    For bot calls, is_outbound must be specified. Otherwise should raise ValueError.
    """
    with pytest.raises(ValueError) as exc_info:
        session_data.set_call_sid(CallType.STREAM, "bot_call_sid", is_outbound=None)
    assert "is_outbound must be specified for bot calls" in str(exc_info.value)


def test_call_sids_bot_ok(session_data):
    """
    Bot calls should be recorded if is_outbound is specified (True or False).
    """
    call_sid = "bot_call_sid"
    session_data.set_call_sid(CallType.STREAM, call_sid, is_outbound=True)
    # If your code truly differentiates between inbound vs. outbound, you can test that logic.
    # For now, just verify we can retrieve it.
    assert session_data.get_call_sid(CallType.STREAM) == call_sid



def test_meta_call_sids(session_data):
    """
    Test setting/getting twilio_stream and conference sid 
    in the session's meta_call_sids.
    """
    # By default, meta_call_sids is None, so let's explicitly set it first
    session_data.meta_call_sids = MetaCallSids()
    
    # Now test set/get twilio_stream_sid
    test_stream_sid = "stream123"
    session_data.set_twilio_stream_sid(test_stream_sid)
    assert session_data.get_twilio_stream_sid() == test_stream_sid
    
    # Test set/get conference_sid
    test_conf_sid = "confSid123"
    session_data.set_conference_sid(test_conf_sid)
    assert session_data.get_conference_sid() == test_conf_sid


def test_ready_for_stream(session_data):
    """
    Test the flags that control whether the session is ready for stream.
    """
    assert session_data.is_ready_for_stream() is False
    session_data.set_ready_for_stream()
    assert session_data.is_ready_for_stream() is True
    session_data.unset_ready_for_stream()
    assert session_data.is_ready_for_stream() is False


def test_add_chat_message_and_get_chat_history(session_data):
    """
    Test chat messages can be added and retrieved in order.
    """
    msg1 = ChatMessage(role="user", content="Hello")
    msg2 = ChatMessage(role="bot", content="Hi there!")
    
    session_data.add_to_chat_history("user", "Hello")
    session_data.add_to_chat_history("assistant", "Hi there!")
    
    history = session_data.get_chat_history()
    assert len(history) == 2
    assert history[0].role == "user"
    assert history[0].content == "Hello"
    assert history[1].role == "assistant"
    assert history[1].content == "Hi there!"
