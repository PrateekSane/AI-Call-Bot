from typing import Dict, Optional, Tuple
from pydantic import BaseModel, Field
from backend.core.constants import ResponseMethod, CallType, CallDirection
from dataclasses import dataclass, field


class UserInformation(BaseModel):
    """User information for the system prompt"""
    user_name: str
    user_email: str
    reason_for_call: str
    account_number: str
    additional_info: Dict[str, str] = Field(default_factory=dict)


@dataclass
class BotCall:
    call_sid: str
    call_type: CallType  # This will only contain bot call types

@dataclass
class CallSids:
    # Key can be (CallType, bool) if we need inbound/outbound, or just CallType
    # if inbound/outbound is only relevant for BOT calls.
    storage: Dict[Tuple[CallType, Optional[bool]], str] = None
    call_type_to_direction: Dict[CallType, CallDirection] = None

    def __post_init__(self):
        if self.storage is None:
            self.storage = {}
        if self.call_type_to_direction is None:
            self.call_type_to_direction = {}

    def set_sid(self, call_type: CallType, call_sid: str, is_outbound: Optional[bool] = None):
        self.storage[call_type] = call_sid
        if is_outbound is not None:
            self.call_type_to_direction[call_type] = CallDirection.OUTBOUND if is_outbound else CallDirection.INBOUND

    def get_sid(self, call_type: CallType) -> Optional[str]:
        key = call_type
        return self.storage.get(key)
    
    def get_direction(self, call_type: CallType) -> Optional[CallDirection]:
        return self.call_type_to_direction.get(call_type)

@dataclass
class MetaCallSids:
    twilio_stream: Optional[str] = None
    conference: Optional[str] = None


class ChatMessage(BaseModel):
    """Chat message for a session"""
    role: str
    content: str


class InitiateCallRequest(BaseModel):
    """Main request model for initiating a call"""
    bot_number: str = Field(..., pattern=r'^\+\d{11}$')  # Enforce E.164 format
    cs_number: str = Field(..., pattern=r'^\+\d{11}$')
    user_number: str = Field(..., pattern=r'^\+\d{11}$')
    user_info: UserInformation 
    poopballsack:str = "poopballsack"


class OpenAIResponseFormat(BaseModel):
    """Response format for OpenAI API to handle Twilio response"""
    response_method: ResponseMethod
    response_content: str 