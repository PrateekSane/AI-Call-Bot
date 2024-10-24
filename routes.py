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
        action='/join_conference',
        method='POST',
        caller_id=TWILIO_NUMBER 
    )
    dial.number(
        CUSTOMER_SERVICE_NUMBER,
        status_callback='/dial_events',
        status_callback_event='initiated ringing answered completed',
        status_callback_method='POST'
    )
    resp.append(dial)
    print(str(resp))
    return str(resp)

@main.route("/dial_events", methods=['POST'])
def dial_events():
    params = request.form.to_dict()
    child_call_sid = params.get('CallSid')
    child_call_status = params.get('CallStatus')
    logger.info(f"Call {child_call_status} with child: {child_call_sid}")
        
    
    if child_call_status == 'initiated':
        logger.info("Dial initiated")
    elif child_call_status == 'ringing':
        logger.info("Dial ringing")
    elif child_call_status == 'in-progress':
        call_handler.set_number_sid(child_call_sid, CUSTOMER_SERVICE_NUMBER)
        call_handler.add_call_to_conference(child_call_sid)
    elif child_call_status == 'completed':
        logger.info("Dial completed")

    return '', 200 

@main.route("/join_conference", methods=['GET', 'POST'])
def join_conference():
    """Provide TwiML to join the conference"""
    resp = VoiceResponse()
    dial = Dial()
    dial.conference(
        "ABCDE",  # has to be unique
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
    if event == 'conference-start' or event == 'conference-end':
        logger.info(' '.join(event.split('-')) + 'ing')
        return '', 200

    participant_call_sid = params.get('CallSid')

    caller_number = call_handler.get_number_from_sid(participant_call_sid)
    call_handler.increment_caller_join_count(participant_call_sid)
    logger.info(f"Conference Event: {event}, CallSid: {participant_call_sid}, CALLER NUMBER: {caller_number}")

    if event == 'participant-join':
        if call_handler.is_user_number(caller_number):
            logger.info("User has joined the conference.")
            # if that user was already in the conference and is now rejoining
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