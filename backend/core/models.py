from typing import Dict, Optional, List
from pydantic import BaseModel, Field


class UserInformation(BaseModel):
    """User information for the system prompt"""
    user_name: str
    user_email: str
    reason_for_call: str
    account_number: str
    additional_info: Dict[str, str] = Field(default_factory=dict)


class CallSids(BaseModel):
    """Track all call SIDs for a session"""
    outbound_bot_sid: Optional[str] = None
    inbound_bot_sid: Optional[str] = None
    customer_service_sid: Optional[str] = None
    user_sid: Optional[str] = None


class ChatMessage(BaseModel):
    """Chat message for a session"""
    role: str
    content: str


class SessionData(BaseModel):
    """All data associated with a call session"""
    session_id: str
    conference_name: str
    conference_sid: Optional[str] = None
    twilio_stream_sid: Optional[str] = None
    
    # Phone numbers
    bot_number: Optional[str] = None
    cs_number: Optional[str] = None
    user_number: Optional[str] = None
    
    # Call SIDs
    call_sids: CallSids = Field(default_factory=CallSids)
    
    # User information
    user_info: Optional[UserInformation] = None

    chat_history: Optional[List[ChatMessage]] = None


class InitiateCallRequest(BaseModel):
    """Main request model for initiating a call"""
    bot_number: str = Field(..., pattern=r'^\+\d{11}$')  # Enforce E.164 format
    cs_number: str = Field(..., pattern=r'^\+\d{11}$')
    user_number: str = Field(..., pattern=r'^\+\d{11}$')
    user_info: UserInformation 


class OpenAIResponseFormat(BaseModel):
    response_method: str