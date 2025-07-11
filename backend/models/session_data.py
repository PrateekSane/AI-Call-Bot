from typing import Optional, List
from datetime import datetime

from backend.models.models import CallSids, UserInformation, ChatMessage, CallType,  MetaCallSids
from backend.core.constants import CallInfo

class SessionData:
    """
    All data associated with a call session.
    A regular class with an explicit constructor, plus getters/setters.
    """

    def __init__(self, session_id: str, conference_name: str, user_info: Optional[UserInformation] = None):
        # Required fields
        self.session_id = session_id
        self.conference_name = conference_name
        self.user_info: Optional[UserInformation] = user_info

        # Optional fields
        self.meta_call_sids: Optional[MetaCallSids] = None
        self.bot_number: Optional[str] = None
        self.cs_number: Optional[str] = None
        self.user_number: Optional[str] = None
        self.ready_for_stream: bool = False

        # Call SIDs and chat messages default to empty structures
        self.call_sids = CallSids()  # or pass as a param if you prefer
        self.chat_history: List[ChatMessage] = []

        self.time_created: datetime = datetime.now()

    # --- Conference SID ---
    def set_call_sid(self, call_type: CallType, call_sid: str, is_outbound: Optional[bool] = None):
        if call_type.is_bot_call:
            if is_outbound is None:
                raise ValueError(f"is_outbound must be specified for bot calls")
            self.call_sids.set_sid(call_type, call_sid, is_outbound)
        elif call_type == CallType.USER or call_type == CallType.CUSTOMER_SERVICE:
            self.call_sids.set_sid(call_type, call_sid)
        else:
            raise ValueError(f"Invalid call type: {call_type}")

    def get_call_sid(self, call_type: CallType) -> Optional[str]:
        return self.call_sids.get_sid(call_type)

    # --- Call Metadata SIDs ---
    def set_twilio_stream_sid(self, twilio_stream_sid: str):
        self.meta_call_sids.twilio_stream = twilio_stream_sid

    def get_twilio_stream_sid(self) -> Optional[str]:
        return self.meta_call_sids.twilio_stream

    def set_conference_sid(self, conference_sid: str):
        self.meta_call_sids.conference = conference_sid

    def get_conference_sid(self) -> Optional[str]:
        return self.meta_call_sids.conference

    def get_conference_name(self) -> Optional[str]:
        return self.conference_name

    # --- Bot Number ---
    def set_bot_number(self, bot_number: str):
        self.bot_number = bot_number

    def get_bot_number(self) -> Optional[str]:
        return self.bot_number

    # --- CS Number ---
    def set_cs_number(self, cs_number: str):
        self.cs_number = cs_number

    def get_cs_number(self) -> Optional[str]:
        return self.cs_number

    # --- User Number ---
    def set_user_number(self, user_number: str):
        self.user_number = user_number

    def get_user_number(self) -> Optional[str]:
        return self.user_number

    # --- User Info ---
    def set_user_info(self, user_info: UserInformation):
        self.user_info = user_info

    def get_user_info(self) -> Optional[UserInformation]:
        return self.user_info

    # --- Stream Ready ---
    def set_ready_for_stream(self):
        self.ready_for_stream = True

    def unset_ready_for_stream(self):
        self.ready_for_stream = False

    def is_ready_for_stream(self) -> bool:
        return self.ready_for_stream

    # --- Chat History ---
    def add_to_chat_history(self, role: str, content: str):
        self.chat_history.append(ChatMessage(role=role, content=content))

    def get_chat_history(self) -> List[ChatMessage]:
        return self.chat_history
