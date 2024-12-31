import threading
import uuid
from typing import Dict, Any, Optional

from constants import CallInfo
from utils import logger


class CallManager:
    def __init__(self):
        self._lock = threading.Lock()
        # session_data keyed by a unique session_id
        # Each session might contain bot_call_sid, cs_call_sid, user_call_sid, etc.
        self._sessions: Dict[str, Dict[str, Any]] = {}
        
        # A quick lookup of call_sid -> session_id
        self._call_to_session: Dict[str, str] = {}

        # New mapping for bot numbers
        self._number_to_session: Dict[str, str] = {}

    def create_new_session(self) -> str:
        """Create a new session_id and store an empty session."""
        with self._lock:
            session_id = str(uuid.uuid4())
            conference_name = str(uuid.uuid4())
            self._sessions[session_id] = {
                CallInfo.SESSION: session_id,
                CallInfo.OUTBOUND_BOT_SID: None,
                CallInfo.INBOUND_BOT_SID: None,
                CallInfo.CUSTOMER_SERVICE_SID: None,
                CallInfo.USER_SID: None,
                CallInfo.CONFERENCE_SID: None,
                CallInfo.CONFERENCE_NAME: conference_name,
                "bot_number": None,
                "cs_number": None,
                "target_number": None,
                "system_info": {}
            }
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
            if session_id in self._sessions:
                self._sessions[session_id][key] = value
                # If setting bot_number, update the number_to_session mapping
                if key == "bot_number":
                    self._number_to_session[value] = session_id
            else:
                logger.error(f"Session {session_id} not found")

    def get_session_for_call(self, call_sid: str) -> Optional[Dict[str, Any]]:
        """Given a callSid, return the session dict it belongs to, or None."""
        with self._lock:
            session_id = self._call_to_session.get(call_sid)
            if session_id:
                return self._sessions.get(session_id)
            return None

    def get_session_by_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._sessions.get(session_id)

    def get_conference_name(self, session_id: str) -> Optional[str]:
        with self._lock:
            return self._sessions.get(session_id, {}).get(CallInfo.CONFERENCE_NAME)

    def get_session_by_number(self, bot_number: str) -> Optional[Dict[str, Any]]:
        """Get session information using the bot number."""
        with self._lock:
            session_id = self._number_to_session.get(bot_number)
            return self._sessions.get(session_id) if session_id else None

    def delete_session(self, session_id: str):
        """Clean up session data once it's no longer needed."""
        with self._lock:
            if session_id in self._sessions:
                # Remove bot number mapping
                bot_number = self._sessions[session_id].get("bot_number")
                if bot_number:
                    self._number_to_session.pop(bot_number, None)
                
                # Remove call mappings
                for call_sid, sid in list(self._call_to_session.items()):
                    if sid == session_id:
                        del self._call_to_session[call_sid]
                
                del self._sessions[session_id]

# Singleton
call_manager = CallManager()