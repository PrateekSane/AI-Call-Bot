from utils import logger
from constants import TWILIO_NUMBER, TARGET_NUMBER, CUSTOMER_SERVICE_NUMBER, FLASK_ADDRESS, CONFERENCE_NAME



class CallHandler:
    def __init__(self, twilio_client):
        self.twilio_client = twilio_client

        self.sid_to_number = {}
        self.caller_join_count = {}

        self.parent_call_sid = None
        self.child_call_sids = []

    def reset(self):
        self.sid_to_number = {}
        self.caller_join_count = {}

    def add_call_to_conference(self, sid):
        self.twilio_client.calls(sid).update(
            url=FLASK_ADDRESS + '/join_conference',
            method='POST'
        )

    def handle_conference_join(self, sid):
        self.increment_caller_join_count(sid)
        print(self.get_participants_in_conference())

        if self.is_user_number(sid):
            logger.info("User has joined the conference.")
            # if that user was already in the conference and is now rejoining
            # TODO: if they leave, join, leave, join back
            if self.get_caller_join_count(sid) == 2:
                self.remove_bot_from_conference()
        elif self.is_bot_number(sid):
            logger.info("Bot has joined the conference.")
        elif self.is_customer_service_number(sid):
            logger.info("Customer service has joined the conference.")
        else:
            logger.info(f"number not recognized {sid} {self.get_number_from_sid(sid)}")

    def handle_conference_leave(self, sid):
        # If person leaves, call the bot to join the conference
        # TODO: CHECK IF THE CUSTOMER SERVICE STILL IN THE CALL

        print(self.get_participants_in_conference())
        customer_service_holding = True 
        if self.is_user_number(sid):
            # if customer_service_holding:
            #     self.start_bot_listening(self.child_call_sid)
            #     logger.info("Starting the listening bot")
            logger.info("User has left the conference")
        elif self.is_customer_service_number(sid):
            logger.info("Customer service has left the conference.")
        else:
            logger.info(f"number not recognized {sid} {self.get_number_from_sid(sid)}")

    def set_parent_call_sid(self, parent_call_sid, number):
        self.parent_call_sid = parent_call_sid
        self.set_number_sid(parent_call_sid, number)
    
    def set_child_call_sid(self, child_call_sid, number):
        self.child_call_sid = child_call_sid
        self.set_number_sid(child_call_sid, number)
    
    def set_bot_call_sid(self, bot_call_sid, number):
        self.bot_call_sid = bot_call_sid
        self.set_number_sid(bot_call_sid, number)

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

    def is_user_number(self, sid):
        number = self.get_number_from_sid(sid)
        if not number:
            return False
        
        return number == TARGET_NUMBER 

    def is_bot_number(self, sid):
        number = self.get_number_from_sid(sid)
        if not number:
            return False
        
        return number == TWILIO_NUMBER

    def is_customer_service_number(self, sid):
        number = self.get_number_from_sid(sid)
        if not number:
            return False
        
        return number == CUSTOMER_SERVICE_NUMBER 

    def print_people_in_conference(self):
        conferences = self.twilio_client.conferences.list()
        participants = self.twilio_client.conferences(conferences[0].sid).participants.list()
        logger.info(f"conference participants: {participants}")
    
    def get_participants_in_conference(self):
        conferences = self.twilio_client.conferences.list()
        participants = self.twilio_client.conferences(conferences[0].sid).participants.list()
        return participants