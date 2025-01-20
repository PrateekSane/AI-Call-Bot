import threading
import uuid
from typing import Dict, Optional, Any, Union, List

from backend.core.constants import CallInfo, UserInformationKeys, CallType
from backend.core.models import SessionData, CallSids, ChatMessage, BotCall
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

    def link_call_to_session(self, call_sid: str, session_id: str, call_type: CallType, is_outbound: Optional[bool] = None):
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
            
            # Handle based on call type
            if call_type.is_bot_call:
                if is_outbound is None:
                    raise ValueError(f"is_outbound must be specified for bot calls")
                key = CallInfo.OUTBOUND_BOT_SID if is_outbound else CallInfo.INBOUND_BOT_SID
                self.set_session_value(session_id, key, (call_sid, call_type))
            else:
                # Handle user or CS calls
                key = (CallInfo.USER_SID if call_type == CallType.USER 
                      else CallInfo.CUSTOMER_SERVICE_SID)
                self.set_session_value(session_id, key, call_sid)

    def set_session_value(self, session_id: str, key: Union[str, CallInfo], value: Any):
        """Set a particular field in a session."""
        with self._lock:
            if session_id not in self._sessions:
                logger.error(f"Session {session_id} not found")
                return
                
            session = self._sessions[session_id]
            key = self._get_key_value(key)
            
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
            elif key in {CallInfo.OUTBOUND_BOT_SID.value, CallInfo.INBOUND_BOT_SID.value}:
                self._handle_bot_call_sid(session, key, value)
            
            elif key == CallInfo.CUSTOMER_SERVICE_SID.value:
                session.call_sids.customer_service = value
            elif key == CallInfo.USER_SID.value:
                session.call_sids.user = value

    def get_session_value(self, session_id: str, key: Union[str, CallInfo]) -> Optional[Any]:
        """Get a particular field from a session."""
        with self._lock:
            if session_id not in self._sessions:
                logger.error(f"Session {session_id} not found")
                return None
            
            session = self._sessions[session_id]
            key = self._get_key_value(key)
            
            # Get the appropriate field based on the key
            if key == CallInfo.BOT_NUMBER.value:
                return session.bot_number
            elif key == CallInfo.CS_NUMBER.value:
                return session.cs_number
            elif key == CallInfo.USER_NUMBER.value:
                return session.user_number
            elif key == CallInfo.CONFERENCE_SID.value:
                return session.conference_sid
            elif key == CallInfo.TWILIO_STREAM_SID.value:
                return session.twilio_stream_sid
            elif key == CallInfo.USER_INFO.value:
                return session.user_info
            # Handle call SIDs
            elif key == CallInfo.OUTBOUND_BOT_SID.value:
                return session.call_sids.outbound_bots
            elif key == CallInfo.INBOUND_BOT_SID.value:
                return session.call_sids.inbound_bots
            elif key == CallInfo.CUSTOMER_SERVICE_SID.value:
                return session.call_sids.customer_service
            elif key == CallInfo.USER_SID.value:
                return session.call_sids.user
            
            return None
    
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

    def set_stream_ready(self, session_id: str, ready: bool = True):
        """Set whether the session is ready to begin streaming."""
        with self._lock:
            if session_id not in self._sessions:
                logger.error(f"Session {session_id} not found")
                return
            self._sessions[session_id].ready_for_stream = ready

    def is_stream_ready(self, session_id: str) -> bool:
        """Check if the session is ready to begin streaming."""
        with self._lock:
            if session_id not in self._sessions:
                logger.error(f"Session {session_id} not found")
                return False
            return self._sessions[session_id].ready_for_stream

    def add_to_chat_history(self, session_id: str, role: str, content: str):
        """Add a message to the session's chat history."""
        with self._lock:
            if session_id not in self._sessions:
                logger.error(f"Session {session_id} not found")
                return
            self._sessions[session_id].chat_history.append(
                ChatMessage(role=role, content=content)
            )

    def get_chat_history(self, session_id: str) -> List[Dict[str, str]]:
        """Get the chat history for a session."""
        with self._lock:
            if session_id not in self._sessions:
                logger.error(f"Session {session_id} not found")
                return []
            return [
                {"role": msg.role, "content": msg.content} 
                for msg in self._sessions[session_id].chat_history
            ]

    def _get_key_value(self, key: Union[str, CallInfo, UserInformationKeys]) -> str:
        """Convert enum to string if needed."""
        if isinstance(key, (CallInfo, UserInformationKeys)):
            return key.value
        return key

    def get_bot_calls(self, session_id: str, is_outbound: bool = True) -> Dict[str, BotCall]:
        """Get all bot calls of a specific direction (outbound/inbound)."""
        key = CallInfo.OUTBOUND_BOT_SID if is_outbound else CallInfo.INBOUND_BOT_SID
        return self.get_session_value(session_id, key) or {}

    def get_bot_call_by_type(self, session_id: str, call_type: CallType, is_outbound: bool = True) -> Optional[BotCall]:
        """Get a bot call by its type."""
        if not call_type.is_bot_call:
            raise ValueError(f"Call type {call_type} is not a bot call type")
        
        bot_calls = self.get_bot_calls(session_id, is_outbound)
        for bot_call in bot_calls.values():
            if bot_call.call_type == call_type:
                return bot_call
        return None

    def _handle_bot_call_sid(self, session: SessionData, key: str, value: Any):
        """Encapsulated method to handle bot call SIDs."""
        if isinstance(value, tuple) and len(value) == 2:
            call_sid, bot_type = value
            if key == CallInfo.OUTBOUND_BOT_SID.value:
                session.call_sids.outbound_bots[call_sid] = BotCall(
                    call_sid=call_sid,
                    call_type=bot_type
                )
            elif key == CallInfo.INBOUND_BOT_SID.value:
                session.call_sids.inbound_bots[call_sid] = BotCall(
                    call_sid=call_sid,
                    call_type=bot_type
                )
        else:
            raise ValueError(f"Invalid value for {key}: {value}")

# Singleton
call_manager = CallManager()