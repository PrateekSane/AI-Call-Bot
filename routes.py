from flask import request, Blueprint, g
from twilio.twiml.voice_response import VoiceResponse, Gather, Dial, Start
from utils import logger, twilio_client
import requests
from datetime import datetime
from constants import TWILIO_NUMBER, TARGET_NUMBER, CONFERENCE_NAME, WEBSOCKET_ADDRESS, FLASK_ADDRESS

CUSTOMER_SERVICE_NUMBER = '+14692105627'

main = Blueprint('main', __name__)
number_to_sid = {}
caller_join_count = {}

@main.route("/", methods=['GET', 'POST'])
def handle_call():
    """Respond to incoming calls and start audio processing"""
    resp = VoiceResponse()

    logger.info("Starting call")

    number_to_sid[TARGET_NUMBER] = request.form.get('CallSid')

    logger.info(f"User CallSid: {number_to_sid[TARGET_NUMBER]}")

    # Dial the customer service number with action to handle call end
    dial = Dial(
        action='/call_ended',  # When the <Dial> ends, Twilio will request /call_ended
        method='POST',
        caller_id=TWILIO_NUMBER  # Set caller ID to your Twilio number
    )
    dial.number(
        CUSTOMER_SERVICE_NUMBER,
        status_callback='/dial_events',
        status_callback_event='initiated ringing answered completed',
        status_callback_method='POST'
    )
    
    resp.append(dial)
    return str(resp)


@main.route("/dial_events", methods=["GET", 'POST'])
def dial_events():
    params = request.form.to_dict()
    dial_call_sid = params.get('CallSid')
    dial_call_status = params.get('CallStatus')

    number_to_sid[CUSTOMER_SERVICE_NUMBER] = dial_call_sid

    logger.info(f"Dial Event: DialCallSid: {dial_call_sid}, DialCallStatus: {dial_call_status}")

    if dial_call_status == 'initiated':
        logger.info("Dial initiated")
    elif dial_call_status == 'ringing':
        logger.info("Dial ringing")
    elif dial_call_status == 'in-progress':
        logger.info("Dial answered")
        if dial_call_sid:
            merge_calls_into_conference(number_to_sid[TARGET_NUMBER], dial_call_sid)
    elif dial_call_status == 'completed':
        logger.info("Dial completed")

    return '', 200


def merge_calls_into_conference(user_call_sid, customer_service_call_sid):
    """Redirect both call legs into a conference"""
    # Redirect the customer service call into the conference
    # need to make less boof
    # has to be first otherwise cuts out
    if customer_service_call_sid:
        try:
            call = twilio_client.calls(customer_service_call_sid).fetch()
            if call.status in ['in-progress', 'ringing', 'queued']:
                twilio_client.calls(customer_service_call_sid).update(
                    url=FLASK_ADDRESS + '/join_conference',
                    method='POST'
                )
                logger.info("Customer service call redirected to conference")
            else:
                logger.error(f"Customer service call cannot be redirected. Current status: {call.status}")
        except Exception as e:
                logger.error(f"Error redirecting customer service call: {e}")

    # Redirect the user's call into the conference
    logger.info(f"Merging calls into conference")
    if user_call_sid:
        twilio_client.calls(user_call_sid).update(
            url=FLASK_ADDRESS + '/join_conference',
            method='POST'
        )
        logger.info("User call redirected to conference")
    else:
        logger.error("User CallSid not found")

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
        status_callback_event='join leave',
        status_callback_method='POST'
    )
    resp.append(dial)
    return str(resp)


@main.route("/conference_events", methods=['POST'])
def conference_events():
    params = request.form.to_dict()
    event = params.get('StatusCallbackEvent')
    participant_call_sid = params.get('CallSid')
    caller_number = next((key for key, value in number_to_sid.items() if value == participant_call_sid), None)
    caller_join_count[caller_number] = caller_join_count.get(caller_number, 0) + 1
    logger.info(f"Conference Event: {event}, Caller: {caller_number}, CallSid: {participant_call_sid}")

    if event == 'participant-leave':
        if is_user_number(caller_number):
            logger.info("User has left the conference.")
            # Call the bot to join the conference
            call_bot()
        elif is_customer_service_number(caller_number):
            logger.info("Customer service has left the conference.")
    elif event == 'participant-join':
        if is_user_number(caller_number):
            # assuming that user was already in the conference and is now rejoining
            logger.info("User has joined the conference.")
            """
            if caller_join_count[caller_number] == 2:
                remove_bot_from_conference()
            """
            remove_bot_from_conference()
        elif is_customer_service_number(caller_number):
            logger.info("Customer service has joined the conference.")
        elif is_bot_number(caller_number):
            logger.info("Bot has joined the conference.")

    return '', 200


def call_bot():
    """Call the bot and have it join the conference"""
    call = twilio_client.calls.create(
        to=TWILIO_NUMBER,
        from_=TWILIO_NUMBER,
        url=FLASK_ADDRESS + '/bot_join_conference',
        method='POST'
    )
    logger.info("Bot called to join the conference")
    return call


@main.route("/bot_join_conference", methods=['GET', 'POST'])
def bot_join_conference():
    response = VoiceResponse()

    start = Start()
    start.stream(
        name='BotMediaStream',
        url=f"wss://{WEBSOCKET_ADDRESS}/media"
    )
    response.append(start)

    # Join the conference
    dial = Dial()
    dial.conference(
        CONFERENCE_NAME,
        start_conference_on_enter=True,
        end_conference_on_exit=False
    )
    response.append(dial)

    return str(response)

def remove_bot_from_conference():
    """Remove the bot from the conference"""
    # Find the bot's participant SID
    conferences = twilio_client.conferences.list(
        friendly_name=CONFERENCE_NAME,
        status='in-progress'
    )
    if conferences:
        conference_sid = conferences[0].sid
        participants = twilio_client.conferences(conference_sid).participants.list()
        for participant in participants:
            if participant.call_sid != TARGET_NUMBER:
                # Assuming the bot is the other participant
                participant.delete()
                logger.info("Bot has been removed from the conference.")


@main.route("/call_ended", methods=['POST'])
def call_ended():
    resp = VoiceResponse()
    logger.info("Call ended")
    return str(resp)


def is_user_number(caller_number):
    # Normalize numbers if necessary
    return caller_number == TARGET_NUMBER

def is_bot_number(caller_number):
    # Replace with your bot's number if applicable
    return caller_number == TWILIO_NUMBER

def is_customer_service_number(caller_number):
    return caller_number == CUSTOMER_SERVICE_NUMBER


@main.route("/test", methods=['GET'])
def test():
    """A simple test endpoint that returns 'Hello, World!'"""

    return "Hello, World!"