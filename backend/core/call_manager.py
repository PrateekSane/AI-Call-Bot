import threading
import uuid
from typing import Dict, Optional, Any

from backend.core.constants import CallInfo
from backend.core.models import SessionData, CallSids
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
            
            session = SessionData(
                session_id=session_id,
                conference_name=conference_name,
                call_sids=CallSids()
            )
            
            self._sessions[session_id] = session
            return session_id

    def link_call_to_session(self, call_sid: str, session_id: str):
        """Associate a callSid with an existing session."""
        with self._lock:
            if session_id not in self._sessions:
                logger.error(f"Session {session_id} not found")
                return
            self._call_to_session[call_sid] = session_id

    def set_session_value(self, session_id: str, key: str, value: Any):
        """Set a particular field in a session."""
        with self._lock:
            if session_id not in self._sessions:
                logger.error(f"Session {session_id} not found")
                return
                
            session = self._sessions[session_id]
            
            # Update the appropriate field based on the key
            if key == CallInfo.BOT_NUMBER.value:
                session.bot_number = value
                self._number_to_session[value] = session_id
            elif key == CallInfo.CS_NUMBER.value:
                session.cs_number = value
            elif key == CallInfo.USER_NUMBER.value:
                session.user_number = value
            elif key == CallInfo.CONFERENCE_SID.value:
                session.conference_sid = value
            elif key == CallInfo.TWILIO_STREAM_SID.value:
                session.twilio_stream_sid = value
            elif key == CallInfo.USER_INFO.value:
                session.user_info = value
            # Handle call SIDs
            elif key == CallInfo.OUTBOUND_BOT_SID.value:
                session.call_sids.outbound_bot = value
            elif key == CallInfo.INBOUND_BOT_SID.value:
                session.call_sids.inbound_bot = value
            elif key == CallInfo.CUSTOMER_SERVICE_SID.value:
                session.call_sids.customer_service = value
            elif key == CallInfo.USER_SID.value:
                session.call_sids.user = value

    def get_session_for_call(self, call_sid: str) -> Optional[SessionData]:
        """Given a callSid, return the session it belongs to, or None."""
        with self._lock:
            session_id = self._call_to_session.get(call_sid)
            return self._sessions.get(session_id) if session_id else None

    def get_session_by_id(self, session_id: str) -> Optional[SessionData]:
        with self._lock:
            return self._sessions.get(session_id)

    def get_conference_name(self, session_id: str) -> Optional[str]:
        with self._lock:
            session = self._sessions.get(session_id)
            return session.conference_name if session else None

    def get_session_by_number(self, bot_number: str) -> Optional[SessionData]:
        """Get session using the bot number."""
        with self._lock:
            session_id = self._number_to_session.get(bot_number)
            return self._sessions.get(session_id) if session_id else None

    def delete_session(self, session_id: str):
        """Clean up session data once it's no longer needed."""
        with self._lock:
            if session_id in self._sessions:
                session = self._sessions[session_id]
                
                # Remove bot number mapping
                if session.bot_number:
                    self._number_to_session.pop(session.bot_number, None)
                
                # Remove call mappings
                for call_sid, sid in list(self._call_to_session.items()):
                    if sid == session_id:
                        del self._call_to_session[call_sid]
                
                del self._sessions[session_id]


# Singleton
call_manager = CallManager()