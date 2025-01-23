from typing import Dict, Optional, List
from pydantic import BaseModel, Field
from backend.core.constants import ResponseMethod, CallType
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
    outbound_bots: Dict[str, BotCall] = field(default_factory=dict)  # call_sid -> BotCall
    inbound_bots: Dict[str, BotCall] = field(default_factory=dict)   # call_sid -> BotCall
    customer_service: Optional[str] = None
    user: Optional[str] = None

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


class OpenAIResponseFormat(BaseModel):
    """Response format for OpenAI API to handle Twilio response"""
    response_method: ResponseMethod
    response_content: str 