import threading
import uuid
from typing import Dict, Optional, Any, Union, List

from backend.core.constants import CallInfo, CallType
from backend.models.session_data import SessionData
from backend.core.models import CallSids, ChatMessage, BotCall
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
                call_sids=CallSids()
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
            if session_id not in self._sessions:
                logger.error(f"Session {session_id} not found")
                return
            
            # Link call to session
            self._call_to_session[call_sid] = session_id
            self._sessions[session_id].set_call_sid(call_type, call_sid, is_outbound)
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
            session_id = self._number_to_session.get(bot_number)
            # TODO: have check for multiple sessions in the caller
            if not session_id:
                logger.error(f"Bot number {bot_number} not found in any session")
                return None

            return self._sessions.get(session_id)

    def delete_session(self, session_id: str):
        """Clean up session data once it's no longer needed."""
        with self._lock:
            if session_id in self._sessions:
                session = self._sessions[session_id]
                
                # Remove bot number mapping
                if session.bot_number:
                    self._number_to_session = {k: v for k, v in self._number_to_session.items() if not any(sid == session_id for sid, _ in v)}
                
                # Remove call mappings
                for call_sid, sid in list(self._call_to_session.items()):
                    if sid == session_id:
                        del self._call_to_session[call_sid]
                
                del self._sessions[session_id]

# Singleton
call_manager = CallManager()