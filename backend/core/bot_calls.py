from abc import ABC, abstractmethod
from typing import Optional
from twilio.rest.api.v2010.account.call import Call as TwilioCall

class BotCall(ABC):
    def __init__(self, session_id: str, bot_number: str):
        self.session_id = session_id
        self.bot_number = bot_number
        self.call_sid: Optional[str] = None
        self.default_call = False
        
    @abstractmethod
    def get_url_path(self) -> str:
        """Return the URL path this bot instance should connect to"""
        pass
    
    def set_call(self, call: TwilioCall):
        """Set the Twilio call object for this bot instance"""
        self.call_sid = call.sid

class ConferenceBot(BotCall):
    def __init__(self, session_id: str, bot_number: str):
        super().__init__(session_id, bot_number)
        self.default_call = True

    def get_url_path(self) -> str:
        return f"/caller_join_conference/{self.session_id}"

class StreamBot(BotCall):
    def get_url_path(self) -> str:
        return f"/incoming-call"

class RecordingBot(BotCall):
    def get_url_path(self) -> str:
        return f"/record_call/{self.session_id}"

class PhoneTreeBot(BotCall):
    def get_url_path(self) -> str:
        return f"/phone_tree/{self.session_id}" 