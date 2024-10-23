from flask import request, Blueprint, g
from twilio.twiml.voice_response import VoiceResponse, Gather, Dial, Start
from utils import logger, twilio_client
import requests
from datetime import datetime
from constants import TWILIO_NUMBER, TARGET_NUMBER, CONFERENCE_NAME, WEBSOCKET_ADDRESS, CUSTOMER_SERVICE_NUMBER, FLASK_ADDRESS
from call_handler import CallHandler


main = Blueprint('main', __name__)
call_handler = CallHandler(twilio_client)

@main.route("/", methods=['GET', 'POST'])
def handle_call():
    """Respond to incoming calls and start audio processing"""
    resp = VoiceResponse()
    #call_handler.reset()

    logger.info("Starting call")

    parent_call_sid = request.values.get('CallSid')
    call_handler.set_number_sid(parent_call_sid, TARGET_NUMBER)

    logger.info(f"User CallSid: {parent_call_sid}")

    # Has to be in the same function as calling customer service  
    dial = Dial(
        action=FLASK_ADDRESS + '/join_conference',
        method='POST',
    )
    dial.number(
        CUSTOMER_SERVICE_NUMBER,
        status_callback='/dial_events',
        status_callback_event='initiated ringing answered completed',
        status_callback_method='POST'
    )
    # dial.conference(
    #     CONFERENCE_NAME,
    #     start_conference_on_enter=True,
    #     end_conference_on_exit=False,
    #     status_callback='/conference_events',
    #     status_callback_event='start end join leave',
    #     status_callback_method='POST'
    # )
    # resp.append(dial)

    # # Dial the customer service number into the same conference
    # cst_sv_leg_call_sid = call_handler.dial_customer_service()

    resp.append(dial)
    return str(resp)

@main.route("/dial_events", methods=['POST'])
def dial_events():
    resp = VoiceResponse()    

    params = request.form.to_dict()
    child_call_sid = params.get('CallSid')
    child_call_status = params.get('CallStatus')
    child_call_number = params.get('CallNumber') 

    logger.info(f"Call Answered by {child_call_number}, {child_call_status}")
    if child_call_sid and child_call_status == 'in-progress':
        call_handler.set_number_sid(child_call_sid, CUSTOMER_SERVICE_NUMBER)
        resp.redirect('/join_conference')

    return resp 

@main.route("/join_conference", methods=['GET', 'POST'])
def join_conference():
    """Provide TwiML to join the conference"""
    resp = VoiceResponse()
    dial = Dial()
    dial.conference(
        CONFERENCE_NAME,
        start_conference_on_enter=True,
        end_conference_on_exit=False,
        status_callback='/conference_events',
        status_callback_event='start join leave end',
        status_callback_method='POST'
    )
    resp.append(dial)
    return str(resp)

@main.route("/conference_events", methods=['POST'])
def conference_events():
    params = request.form.to_dict()
    event = params.get('StatusCallbackEvent')
    participant_call_sid = params.get('CallSid')

    logger.info(f"Conference Event: {event}, CallSid: {participant_call_sid}, event: {event}")
    caller_number = call_handler.get_number_from_sid(participant_call_sid)
    logger.info(f"CALLER NUMBER: {caller_number}")
    call_handler.increment_caller_join_count(participant_call_sid)

    if event == 'participant-join':
        if call_handler.is_user_number(caller_number):
            logger.info("User has joined the conference.")
            # assuming that user was already in the conference and is now rejoining
            if call_handler.get_caller_join_count(participant_call_sid) == 2:
                call_handler.remove_bot_from_conference()
        elif call_handler.is_bot_number(caller_number):
            logger.info("Bot has joined the conference.")
        elif call_handler.is_customer_service_number(caller_number):
            logger.info("Customer service has joined the conference.")
    elif event == 'participant-leave':
        # If person leaves, call the bot to join the conference
        if call_handler.is_user_number(caller_number):
            call_handler.start_bot_listening()
            logger.info("User has left the conference. Bringing the listening bot")
        elif call_handler.is_customer_service_number(caller_number):
            logger.info("Customer service has left the conference.")

    return '', 200

# still need to make it join
@main.route("/listening_bot_join_conference", methods=['GET', 'POST'])
def listening_bot_join_conference():
    response = VoiceResponse()

    start = Start()
    start.stream(
        name='BotMediaStream',
        url=f"wss://{WEBSOCKET_ADDRESS}/media"
    )
    response.append(start)

    # # Join the conference
    # dial = Dial()
    # dial.conference(
    #     CONFERENCE_NAME,
    #     start_conference_on_enter=True,
    #     end_conference_on_exit=False
    # )
    # response.append(dial)

    return str(response)


@main.route("/test", methods=['GET'])
def test():
    """A simple test endpoint that returns 'Hello, World!'"""

    return "Hello, World!"