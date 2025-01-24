import pytest
from unittest.mock import patch
from backend.core.call_manager import CallManager
from backend.core.constants import CallType

# Patch the logger globally so no logs print in tests
@pytest.fixture
def mock_logger():
    with patch("backend.core.call_manager.logger") as mock_log:
        yield mock_log

@pytest.fixture
def call_manager():
    return CallManager()


def test_create_new_session(call_manager):
    """
    Test that creating a new session generates a unique session_id and
    that the session is stored internally.
    """
    session_id = call_manager.create_new_session()
    assert session_id is not None, "Session ID should not be None."

    session_data = call_manager.get_session_by_id(session_id)
    assert session_data is not None, "Session data should be retrievable by session ID."
    assert session_data.session_id == session_id, "Session data should have the correct session_id."


def test_check_session_exists_when_no_session(call_manager):
    """
    Test check_session_exists returns None if no session exists for the given number(s).
    """
    result = call_manager.check_session_exists(["+10000000000"])
    assert result is None, "Should return None if no session matches the given number(s)."


def test_check_session_exists_found(call_manager):
    """
    Test check_session_exists returns a matching session if a number was linked.
    """
    # Create a session
    session_id = call_manager.create_new_session()
    # Link a call to that session
    call_manager.link_call_to_session(
        call_sid="abc123",
        call_number="+15551112222",
        session_id=session_id,
        call_type=CallType.CONFERENCE,
        is_outbound=True
    )

    # Now check if the session exists for this number
    result = call_manager.check_session_exists(["+15551112222"])
    assert result is not None, "Should find a session for the existing number."
    number_found, session_found = result
    assert number_found == "+15551112222", "Should return the matching number."
    assert len(session_found) == 1, "Should return a list with one session_id."
    assert session_found[0] == (session_id, "abc123"), "Should return the session id linked to that number."


def test_link_call_to_invalid_session(call_manager, mock_logger):
    """
    Test linking a call to an invalid session logs an error and does not store data.
    """
    call_manager.link_call_to_session(
        call_sid="abc123",
        call_number="+15551112222",
        session_id="non_existent_session",
        call_type=CallType.USER
    )

    # Since session didn't exist, we expect an error log
    mock_logger.error.assert_called_once()
    # The call should not be recorded
    session = call_manager.get_session_by_call_sid("abc123")
    assert session is None, "No valid session should be linked to an invalid session_id."


def test_link_call_to_session_user(call_manager):
    """
    Test linking a USER call to a valid session updates internal mappings.
    """
    # Create a session
    session_id = call_manager.create_new_session()
    call_sid = "sid123"
    call_number = "+15550001111"

    call_manager.link_call_to_session(
        call_sid=call_sid,
        call_number=call_number,
        session_id=session_id,
        call_type=CallType.USER
    )

    # Verify we can retrieve the session by call_sid
    session_data_by_sid = call_manager.get_session_by_call_sid(call_sid)
    assert session_data_by_sid is not None, "Session should be found by call_sid."
    assert session_data_by_sid.session_id == session_id, "Correct session_id should be returned."

    # Verify retrieving session by the session_id still works
    session_data = call_manager.get_session_by_id(session_id)
    assert session_data is not None, "Session should be found by session_id."

    # Verify the call SID is set in the session's call_sids object
    # We'll check via the get_call_sid() helper:
    assert session_data.get_call_sid(CallType.USER) == call_sid, \
        "USER call SID should match the callSid used in link_call_to_session."

    # Check _number_to_session mapping is updated
    # The internal structure is a list of (session_id, call_sid) tuples.
    stored_entries = call_manager._number_to_session.get(call_number, [])
    assert len(stored_entries) == 1, "Expected exactly one (session_id, call_sid) entry."
    assert stored_entries[0] == (session_id, call_sid), "The stored entry should match the linked session/call."


def test_get_session_by_call_sid_invalid(call_manager):
    """
    Test retrieval of a session by a non-existent call SID returns None.
    """
    session = call_manager.get_session_by_call_sid("unknown_sid")
    assert session is None, "Should return None for a callSid that doesn't exist."


def test_get_session_by_id_invalid(call_manager):
    """
    Test retrieval of a session by an invalid session ID returns None.
    """
    session = call_manager.get_session_by_id("not_a_real_session")
    assert session is None, "Should return None for a non-existent session ID."


def test_get_session_by_number_invalid(call_manager):
    """
    Test retrieval of session by a number that doesn't exist returns None.
    """
    session = call_manager.get_session_by_number("+1234567890")
    assert session is None, "Should return None for a number that isn't linked to any session."


def test_get_session_by_number_bot_multiple_calls_same_session(call_manager, mock_logger):
    """
    If multiple bot calls (with different call_types) are linked to the SAME session
    for the same bot number, `get_session_by_number` should return that single session
    without error logs.
    """
    session_id = call_manager.create_new_session()
    bot_number = "+15559990000"

    # First bot call (e.g., CONFERENCE)
    call_sid1 = "bot_sid_1"
    call_manager.link_call_to_session(
        call_sid=call_sid1,
        call_number=bot_number,
        session_id=session_id,
        call_type=CallType.CONFERENCE,
        is_outbound=True
    )

    # Second bot call (e.g., STREAM)
    call_sid2 = "bot_sid_2"
    call_manager.link_call_to_session(
        call_sid=call_sid2,
        call_number=bot_number,
        session_id=session_id,
        call_type=CallType.STREAM,
        is_outbound=False
    )

    # Now attempt to retrieve by bot_number
    session_data = call_manager.get_session_by_number(bot_number)
    assert session_data is not None, "Should return a single session for the known bot number."
    assert session_data.session_id == session_id, "Should match the session we created."

    # We should see no error logs, since we do NOT have multiple sessions
    mock_logger.error.assert_not_called()

    # Check call SIDs recorded properly
    assert session_data.get_call_sid(CallType.CONFERENCE) == call_sid1, \
        "CONFERENCE call SID should match the first call."
    assert session_data.get_call_sid(CallType.STREAM) == call_sid2, \
        "STREAM call SID should match the second call."


def test_get_session_by_number_bot_multiple_sessions(call_manager, mock_logger):
    """
    If the same bot number is linked to different sessions, then `get_session_by_number`
    should detect multiple sessions, log an error, and return None.
    """
    # Create two different sessions
    session_id_1 = call_manager.create_new_session()
    session_id_2 = call_manager.create_new_session()

    bot_number = "+15559990000"

    # Link the same bot number to two different sessions
    call_sid1 = "bot_sid_1"
    call_manager.link_call_to_session(
        call_sid=call_sid1,
        call_number=bot_number,
        session_id=session_id_1,
        call_type=CallType.CONFERENCE,
        is_outbound=True
    )

    call_sid2 = "bot_sid_2"
    call_manager.link_call_to_session(
        call_sid=call_sid2,
        call_number=bot_number,
        session_id=session_id_2,
        call_type=CallType.CONFERENCE,
        is_outbound=False
    )

    # Now attempt to retrieve by bot_number
    session_data = call_manager.get_session_by_number(bot_number)
    assert session_data is None, "Should return None, because multiple sessions share the same bot number."

    # Check an error log was generated about multiple sessions
    mock_logger.error.assert_called()
    # (Optional) You can check the exact message if you want:
    mock_logger.error.assert_any_call(f"Multiple sessions found for bot number {bot_number}")



def test_delete_session(call_manager):
    """
    Test deleting a session removes it from all internal mappings.
    """
    # Create a session and link calls
    session_id = call_manager.create_new_session()
    call_sid_bot = "bot_sid_2"
    call_sid_user = "user_sid_2"
    bot_number = "+18880001111"
    user_number = "+12223334444"

    call_manager.link_call_to_session(call_sid_bot, bot_number, session_id, CallType.CONFERENCE, is_outbound=False)
    call_manager.link_call_to_session(call_sid_user, user_number, session_id, CallType.USER)

    # Sanity checks: The session should exist before deletion
    assert call_manager.get_session_by_id(session_id) is not None
    assert call_manager.get_session_by_call_sid(call_sid_bot) is not None
    assert call_manager.get_session_by_call_sid(call_sid_user) is not None
    assert bot_number in call_manager._number_to_session
    assert user_number in call_manager._number_to_session

    # Now delete the session
    call_manager.delete_session(session_id)

    # Verify session is removed
    assert call_manager.get_session_by_id(session_id) is None, "Session should be deleted."
    assert call_manager.get_session_by_call_sid(call_sid_bot) is None, "Bot SID should be unlinked."
    assert call_manager.get_session_by_call_sid(call_sid_user) is None, "User SID should be unlinked."

    # Because your current delete_session logic removes only the session's bot number 
    # from _number_to_session, you might need to confirm that user_number is also cleared
    # (or accept that it's not cleared automatically). We'll just verify the session_id 
    # is no longer there.
    if bot_number in call_manager._number_to_session:
        for sid_tuple in call_manager._number_to_session[bot_number]:
            assert sid_tuple[0] != session_id, "Deleted session should not be referenced."
    if user_number in call_manager._number_to_session:
        for sid_tuple in call_manager._number_to_session[user_number]:
            assert sid_tuple[0] != session_id, "Deleted session should not be referenced."