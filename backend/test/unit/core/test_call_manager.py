import pytest
import uuid
from unittest.mock import patch

from backend.core.constants import CallInfo, UserInformationKeys, CallType
from backend.core.models import SessionData, CallSids, ChatMessage, BotCall
from backend.utils.utils import logger
from backend.core.call_manager import CallManager


@pytest.fixture
def manager():
    """
    Create a fresh CallManager instance for each test,
    so tests don't interfere with each other.
    """
    return CallManager()


def test_create_new_session(manager):
    """
    Test that create_new_session generates a new UUID-based session_id and stores a blank session.
    """
    session_id = manager.create_new_session()
    assert session_id is not None
    assert isinstance(session_id, str)
    session_data = manager.get_session_by_id(session_id)
    assert session_data is not None
    # Check a valid conference_name is generated
    assert session_data.conference_name is not None
    assert isinstance(session_data.conference_name, str)
    # Verify call_sids is an empty structure
    assert isinstance(session_data.call_sids, CallSids)


def test_link_call_to_session_user_call(manager):
    """
    Test linking a user call to a session, storing the callSid, 
    and verifying it sets the correct session key.
    """
    session_id = manager.create_new_session()
    call_sid = "CA12345USER"
    manager.link_call_to_session(call_sid, session_id, CallType.USER)
    # Check the call->session mapping
    session_data = manager.get_session_for_call(call_sid)
    assert session_data is not None
    assert session_data.session_id == session_id
    # Check that user callSid is stored
    user_sid = manager.get_session_value(session_id, CallInfo.USER_SID)
    assert user_sid == call_sid


def test_link_call_to_session_bot_call_outbound(manager):
    """
    Test linking an outbound bot call. This requires is_outbound=True.
    """
    session_id = manager.create_new_session()
    call_sid = "CABOT123"
    # For a bot call, we must pass is_outbound
    manager.link_call_to_session(call_sid, session_id, CallType.BOT, is_outbound=True)

    session_data = manager.get_session_for_call(call_sid)
    assert session_data is not None
    # Check that the manager set the outbound bot SID
    outbound_bots = manager.get_session_value(session_id, CallInfo.OUTBOUND_BOT_SID)
    assert call_sid in outbound_bots
    bot_call = outbound_bots[call_sid]
    assert bot_call.call_sid == call_sid
    assert bot_call.call_type == CallType.BOT


def test_link_call_to_session_bot_call_inbound(manager):
    """
    Test linking an inbound bot call with is_outbound=False.
    """
    session_id = manager.create_new_session()
    call_sid = "CABOT_IN_999"
    manager.link_call_to_session(call_sid, session_id, CallType.BOT, is_outbound=False)

    inbound_bots = manager.get_session_value(session_id, CallInfo.INBOUND_BOT_SID)
    assert call_sid in inbound_bots
    bot_call = inbound_bots[call_sid]
    assert bot_call.call_sid == call_sid
    assert bot_call.call_type == CallType.BOT


def test_link_call_to_session_missing_is_outbound(manager):
    """
    For a bot call, is_outbound must be specified or it raises a ValueError.
    """
    session_id = manager.create_new_session()
    call_sid = "CABOT_FAIL"
    with pytest.raises(ValueError, match="is_outbound must be specified for bot calls"):
        manager.link_call_to_session(call_sid, session_id, CallType.BOT)


def test_link_call_to_session_nonexistent_session(manager, caplog):
    """
    Linking a call to a non-existent session logs an error.
    """
    call_sid = "CAFAKE"
    manager.link_call_to_session(call_sid, "nonexistent_session", CallType.USER)
    assert "Session nonexistent_session not found" in caplog.text


def test_set_session_value_and_get_session_value(manager):
    """
    Test setting and getting various session values, verifying they are stored correctly.
    """
    session_id = manager.create_new_session()
    manager.set_session_value(session_id, CallInfo.BOT_NUMBER, "+15551234567")
    manager.set_session_value(session_id, CallInfo.CS_NUMBER, "+18005550199")
    manager.set_session_value(session_id, CallInfo.USER_NUMBER, "+16175551212")
    manager.set_session_value(session_id, CallInfo.CONFERENCE_SID, "CF123")
    manager.set_session_value(session_id, CallInfo.TWILIO_STREAM_SID, "TS123")

    # user_info is a dict
    user_info_dict = {
        UserInformationKeys.USER_NAME.value: "Alice",
        UserInformationKeys.USER_EMAIL.value: "alice@example.com",
    }
    manager.set_session_value(session_id, CallInfo.USER_INFO, user_info_dict)

    # now retrieve them
    assert manager.get_session_value(session_id, CallInfo.BOT_NUMBER) == "+15551234567"
    assert manager.get_session_value(session_id, CallInfo.CS_NUMBER) == "+18005550199"
    assert manager.get_session_value(session_id, CallInfo.USER_NUMBER) == "+16175551212"
    assert manager.get_session_value(session_id, CallInfo.CONFERENCE_SID) == "CF123"
    assert manager.get_session_value(session_id, CallInfo.TWILIO_STREAM_SID) == "TS123"
    assert manager.get_session_value(session_id, CallInfo.USER_INFO) == user_info_dict


def test_set_session_value_nonexistent_session(manager, caplog):
    """
    Setting a session value on a nonexistent session logs an error and does nothing.
    """
    manager.set_session_value("bad_session", CallInfo.BOT_NUMBER, "+19999999999")
    assert "Session bad_session not found" in caplog.text


def test_get_session_value_nonexistent_session(manager, caplog):
    """
    Getting a value from a nonexistent session logs an error and returns None.
    """
    val = manager.get_session_value("does_not_exist", CallInfo.USER_NUMBER)
    assert val is None
    assert "Session does_not_exist not found" in caplog.text


def test_get_session_for_call(manager):
    """
    Ensure get_session_for_call returns None if callSid not linked, or the correct session otherwise.
    """
    session_id = manager.create_new_session()
    call_sid = "UNLINKED_CALL"
    # not linked yet -> should be None
    assert manager.get_session_for_call(call_sid) is None

    manager.link_call_to_session(call_sid, session_id, CallType.USER)
    session_data = manager.get_session_for_call(call_sid)
    assert session_data is not None
    assert session_data.session_id == session_id


def test_get_session_by_id(manager):
    """
    Check retrieval by session_id.
    """
    session_id = manager.create_new_session()
    session_data = manager.get_session_by_id(session_id)
    assert session_data is not None
    assert session_data.session_id == session_id

    # non-existing
    assert manager.get_session_by_id("fake_id") is None


def test_get_conference_name(manager):
    session_id = manager.create_new_session()
    conf_name = manager.get_conference_name(session_id)
    session_data = manager.get_session_by_id(session_id)
    assert conf_name == session_data.conference_name

    # non-existing
    assert manager.get_conference_name("fake_id") is None


def test_get_session_by_number(manager):
    session_id = manager.create_new_session()
    manager.set_session_value(session_id, CallInfo.BOT_NUMBER, "+15559990000")

    # Should retrieve session by that bot_number
    found = manager.get_session_by_number("+15559990000")
    assert found is not None
    assert found.session_id == session_id

    # For a non-existing number, returns None
    assert manager.get_session_by_number("+15553334444") is None


def test_delete_session(manager):
    """
    Deleting a session should remove it from internal dicts
    (_sessions, _call_to_session, _number_to_session).
    """
    session_id = manager.create_new_session()
    manager.set_session_value(session_id, CallInfo.BOT_NUMBER, "+12223334444")
    call_sid = "TO_DELETE"
    manager.link_call_to_session(call_sid, session_id, CallType.USER)

    manager.delete_session(session_id)

    # session removed
    assert manager.get_session_by_id(session_id) is None
    # call->session link removed
    assert manager.get_session_for_call(call_sid) is None
    # number->session link removed
    assert manager.get_session_by_number("+12223334444") is None


def test_set_and_is_stream_ready(manager):
    session_id = manager.create_new_session()
    # default is not ready
    assert manager.is_stream_ready(session_id) is False

    manager.set_stream_ready(session_id, True)
    assert manager.is_stream_ready(session_id) is True

    manager.set_stream_ready(session_id, False)
    assert manager.is_stream_ready(session_id) is False


def test_stream_ready_with_nonexistent_session(manager, caplog):
    manager.set_stream_ready("fake_sess", True)
    assert "Session fake_sess not found" in caplog.text
    assert manager.is_stream_ready("fake_sess") is False  # logs error again
    assert "Session fake_sess not found" in caplog.text


def test_add_to_chat_history_and_get_chat_history(manager):
    session_id = manager.create_new_session()
    manager.add_to_chat_history(session_id, "user", "Hello!")
    manager.add_to_chat_history(session_id, "assistant", "Hi there!")
    history = manager.get_chat_history(session_id)
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "Hello!"
    assert history[1]["role"] == "assistant"
    assert history[1]["content"] == "Hi there!"


def test_get_chat_history_nonexistent_session(manager, caplog):
    hist = manager.get_chat_history("some_fake_session")
    assert hist == []
    assert "Session some_fake_session not found" in caplog.text


def test_get_bot_calls(manager):
    """
    Ensure get_bot_calls returns the correct dictionary for outbound or inbound.
    """
    session_id = manager.create_new_session()
    outbound_sid_1 = "OUT123"
    inbound_sid_1 = "IN123"

    # Link calls
    manager.link_call_to_session(outbound_sid_1, session_id, CallType.BOT, is_outbound=True)
    manager.link_call_to_session(inbound_sid_1, session_id, CallType.BOT, is_outbound=False)

    # get outbound
    outbound = manager.get_bot_calls(session_id, is_outbound=True)
    assert outbound_sid_1 in outbound
    # get inbound
    inbound = manager.get_bot_calls(session_id, is_outbound=False)
    assert inbound_sid_1 in inbound


def test_get_bot_call_by_type(manager):
    """
    Test that we can retrieve a specific BotCall by its call type.
    """
    session_id = manager.create_new_session()
    call_sid = "CABOTHELLO"
    manager.link_call_to_session(call_sid, session_id, CallType.BOT, is_outbound=True)

    found = manager.get_bot_call_by_type(session_id, CallType.BOT, is_outbound=True)
    assert found is not None
    assert found.call_sid == call_sid
    assert found.call_type == CallType.BOT


def test_get_bot_call_by_type_not_bot(manager):
    """
    If we ask for a non-bot CallType, it should raise ValueError.
    """
    session_id = manager.create_new_session()
    with pytest.raises(ValueError, match="is not a bot call type"):
        manager.get_bot_call_by_type(session_id, CallType.USER)  # not a bot call


def test_set_session_value_for_bot_call_wrong_format(manager):
    """
    If we call set_session_value for a bot call SID but pass the wrong value format, 
    it should raise ValueError. (We test the _handle_bot_call_sid indirectly.)
    """
    session_id = manager.create_new_session()
    bad_value = "NOT A TUPLE"
    with pytest.raises(ValueError, match="Invalid value for outbound_bot_sid"):
        manager.set_session_value(session_id, CallInfo.OUTBOUND_BOT_SID, bad_value)
