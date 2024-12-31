from enum import Enum

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

class UserInformationKeys(Enum):
    USER_NAME = 'user_name'
    USER_EMAIL = 'user_email'
    REASON_FOR_CALL = 'reason_for_call'
    ACCOUNT_NUMBER = 'account_number'
    ADDITIONAL_INFO = 'additional_info'

SYSTEM_PROMPT_TEMPLATE = """You are the {user_name}'s helpful assistant and you are calling on their behalf to a customer service agent. YOU ARE NOT {user_name}.
You are given the following pieces of information about {user_name}. Use this information to help the customer service agent. Keep your responses concise and to the point.
Make sure you mention the account number when ONLY asked for it. 
ONLY mention the reason for call initially.

User Name: {user_name}
User Email: {user_email}
Reason for call: {reason_for_call}
Account Number: {account_number}
{additional_info}

You need to give the customer service agent the best possible information about the user so that they can help them. 
When you get stuck or you have given the customer service agent all the information you can, say "I need to REDIRECT you to a human agent". 
Do not make up information."""
