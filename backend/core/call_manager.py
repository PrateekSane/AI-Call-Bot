import threading
import uuid
from typing import Dict, Optional

from backend.core.constants import CallType
from backend.models.session_data import SessionData
from backend.models.models import CallSids
from backend.utils.utils import logger


class CallManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._sessions: Dict[str, SessionData] = {}
        self._call_to_session: Dict[str, str] = {}
        self._number_to_session: Dict[str, str] = {}

    def create_new_session(self) -> str:
        """Create a new session_id and store an empty session."""
        with self._lock:
            session_id = str(uuid.uuid4())
            conference_name = str(uuid.uuid4())
            
            session_data = SessionData(
                session_id=session_id,
                conference_name=conference_name,
            )
            
            self._sessions[session_id] = session_data
            return session_id
        
    def check_session_exists(self, call_numbers: list[str]) -> Optional[str]:
        """Check if a session exists for the given call number."""
        with self._lock:
            for call_number in call_numbers:
                if call_number in self._number_to_session:
                    return call_number, self._number_to_session[call_number]
            return None

    def link_call_to_session(self, call_sid: str, call_number: str, session_id: str, call_type: CallType, is_outbound: Optional[bool] = None):
        """
        Associate a callSid with an existing session and set appropriate session values.
        
        Args:
            call_sid: The Twilio call SID
            session_id: The session to link to
            call_type: The type of call (from CallType enum)
            is_outbound: For bot calls, specify if outbound. Must be set if call_type is a bot call.
        """
        with self._lock:
            logger.info(f"Linking call {call_sid} to session {session_id}")
            if session_id not in self._sessions:
                logger.error(f"Session {session_id} not found")
                return
            
            # Link call to session
            self._call_to_session[call_sid] = session_id
            self._sessions[session_id].set_call_sid(call_type, call_sid, is_outbound)
            # Need to have multiple sessions for the same number because of the bot
            if call_number in self._number_to_session:
                self._number_to_session[call_number].append((session_id, call_sid))
            else:
                self._number_to_session[call_number] = [(session_id, call_sid)]
            
    def get_session_by_call_sid(self, call_sid: str) -> Optional[SessionData]:
        """Given a callSid, return the session it belongs to, or None."""
        with self._lock:
            session_id = self._call_to_session.get(call_sid)
            if not session_id:
                logger.error(f"CallSid {call_sid} not found in any session")
                return None

            return self._sessions.get(session_id)

    def get_session_by_id(self, session_id: str) -> Optional[SessionData]:
        with self._lock:
            if session_id not in self._sessions:
                logger.error(f"Session {session_id} not found")
                return None
            return self._sessions.get(session_id)

    def get_session_by_number(self, bot_number: str) -> Optional[SessionData]:
        """Get session using the bot number."""
        with self._lock:
            session_id_pairs = self._number_to_session.get(bot_number)
            # TODO: have check for multiple sessions in the caller
            if not session_id_pairs:
                logger.error(f"Bot number {bot_number} not found in any session")
                return None
            
            unique_session_ids = {session_id for session_id, _ in session_id_pairs}
            if len(unique_session_ids) > 1:
                logger.error(f"Multiple sessions found for bot number {bot_number}")
                return None

            assert len(unique_session_ids) == 1
            session_id = next(iter(unique_session_ids))
            return self._sessions.get(session_id)

    def delete_session(self, session_id: str):
        """Clean up session data once it's no longer needed."""
        with self._lock:
            if session_id in self._sessions:
                # 1. Remove references to this session in _number_to_session
                for number, tuples in list(self._number_to_session.items()):
                    new_tuples = [(sid, c_sid) for (sid, c_sid) in tuples if sid != session_id]
                    if not new_tuples:
                        # If no pairs remain, remove the number entirely
                        del self._number_to_session[number]
                    else:
                        self._number_to_session[number] = new_tuples

                # 2. Remove call_sid -> session_id mappings
                for call_sid, sid in list(self._call_to_session.items()):
                    if sid == session_id:
                        del self._call_to_session[call_sid]

                # 3. Remove the session object
                del self._sessions[session_id]
    
# Singleton
call_manager = CallManager()
