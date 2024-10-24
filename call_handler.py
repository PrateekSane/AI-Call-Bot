from utils import logger
from constants import TWILIO_NUMBER, TARGET_NUMBER, CUSTOMER_SERVICE_NUMBER, FLASK_ADDRESS, CONFERENCE_NAME



class CallHandler:
    def __init__(self, twilio_client):
        self.twilio_client = twilio_client

        self.sid_to_number = {}
        self.caller_join_count = {}
        self.active_call_sid = None

    def reset(self):
        self.sid_to_number = {}
        self.caller_join_count = {}

    # def dial_customer_service(self):
    #     """Dial customer service number and join the conference"""
    #     try:
    #         call = self.twilio_client.calls.create(
    #             to=CUSTOMER_SERVICE_NUMBER,
    #             from_=TWILIO_NUMBER,
    #             url=FLASK_ADDRESS + '/join_conference',
    #             method='POST'
    #         )
    #         self.set_number_sid(CUSTOMER_SERVICE_NUMBER, call.sid)
    #         logger.info(f"Dialed customer service: {call.sid}")

    #         return call.sid 
    #     except Exception as e:
    #         logger.error(f"Error dialing customer service: {e}")

    def add_call_to_conference(self, sid):
        self.twilio_client.calls(sid).update(
            url=FLASK_ADDRESS + '/join_conference',
            method='POST'
        )

    def start_bot_listening(self, call_sid):
        # BEFORE MAKING WORK MAKE SURE THERE IS ABILITY TO END THE CALL
        call = self.twilio_client.calls(call_sid).update(
            url=FLASK_ADDRESS + '/listening_bot_join_conference',
            method='POST'
        )

    def set_number_sid(self, sid, number):
        self.sid_to_number[sid] = number

    def get_number_from_sid(self, sid):
        if sid in self.sid_to_number:
            return self.sid_to_number[sid]
        else:
            raise KeyError(f"Number for sid:'{sid}' not found in call_handler.")

    def get_caller_join_count(self, caller_sid):
        return self.caller_join_count.get(caller_sid)
    
    def increment_caller_join_count(self, caller_sid):
        if caller_sid not in self.caller_join_count:
            self.caller_join_count[caller_sid] = 1
        else:
            self.caller_join_count[caller_sid] += 1


    def remove_bot_from_conference(self):
        """Remove the bot from the conference"""
        # Find the bot's participant SID
        conferences = self.twilio_client.conferences.list(
            friendly_name=CONFERENCE_NAME,
            status='in-progress'
        )

        if conferences:
            conference_sid = conferences[0].sid
            participants = self.twilio_client.conferences(conference_sid).participants.list()
            for participant in participants:
                if self.is_bot_from_sid(participant.call_sid):
                    participant.delete()
                    logger.info("Bot has been removed from the conference.")
                    return True
        return False

    def is_user_number(self, caller_number):
        # Normalize numbers if necessary
        return caller_number == TARGET_NUMBER

    def is_bot_number(self, caller_number):
        # Replace with your bot's number if applicable
        return caller_number == TWILIO_NUMBER

    def is_bot_from_sid(self, sid):
        number = self.get_number_from_sid(sid)
        if not number:
            return False
        
        return number == TWILIO_NUMBER

    def is_customer_service_number(self, caller_number):
        return caller_number == CUSTOMER_SERVICE_NUMBER

    def print_people_in_conference(self):
        conferences = self.twilio_client.conferences.list()
        participants = self.twilio_client.conferences(conferences[0].sid).participants.list()
        logger.info(f"conference participants: {participants}")