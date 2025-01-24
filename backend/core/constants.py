from enum import Enum


class UserInformationKeys(Enum):
    USER_NAME = 'user_name'
    USER_EMAIL = 'user_email'
    REASON_FOR_CALL = 'reason_for_call'
    ACCOUNT_NUMBER = 'account_number'
    ADDITIONAL_INFO = 'additional_info'


class TwilioCallStatus(Enum):
    INITIATED = 'initiated'
    RINGING = 'ringing'
    IN_PROGRESS = 'in-progress'
    COMPLETED = 'completed'

class ResponseMethod(Enum):
    NOOP = 'noop'
    VOICE = 'voice'
    CALL_BACK = 'call_back'
    PHONE_TREE = 'phone_tree'


class CallInfo(Enum):
    SESSION = 'session_id'
    OUTBOUND_BOT_SID = 'outbound_bot_call_sid'
    INBOUND_BOT_SID = 'inbound_bot_call_sid'
    USER_SID = 'user_call_sid'
    CUSTOMER_SERVICE_SID = 'customer_service_call_sid'
    CONFERENCE_SID = 'conference_sid'
    CONFERENCE_NAME = 'conference_name'
    TWILIO_STREAM_SID = 'twilio_stream_sid'
    BOT_NUMBER = 'bot_number'
    CS_NUMBER = 'cs_number'
    USER_NUMBER = 'user_number'
    USER_INFO = 'user_info'


class CallType(Enum):
    # Bot call types
    CONFERENCE = 'conference'
    STREAM = 'stream'
    RECORDING = 'recording'
    PHONE_TREE = 'phone_tree'
    # Other call types
    USER = 'user'
    CUSTOMER_SERVICE = 'customer_service'

    @property
    def is_bot_call(self) -> bool:
        return self in {
            CallType.CONFERENCE,
            CallType.STREAM,
            CallType.RECORDING,
            CallType.PHONE_TREE
        }
