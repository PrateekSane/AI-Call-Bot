from enum import Enum


TWILIO_PHONE_NUMBER = '+12028164470'
TARGET_NUMBER = '+19164729906'
CUSTOMER_SERVICE_NUMBER = '+14692105627'
# CUSTOMER_SERVICE_NUMBER = '+14084976281'

CONFERENCE_NAME = 'applebanana9'

class CallInfo(Enum):
    SESSION = 'session_id'
    OUTBOUND_BOT_SID = 'outbound_bot_call_sid'
    INBOUND_BOT_SID = 'inbound_bot_call_sid'
    USER_SID = 'user_call_sid'
    CUSTOMER_SERVICE_SID = 'customer_service_call_sid'
    CONFERENCE_SID = 'conference_sid'
    CONFERENCE_NAME = 'conference_name'
    TWILIO_STREAM_SID = 'twilio_stream_sid'