from flask import request, Blueprint, g
from twilio.twiml.voice_response import VoiceResponse, Gather, Dial, Start
from utils import logger, twilio_client
import requests
from datetime import datetime
from constants import TWILIO_NUMBER, TARGET_NUMBER, CONFERENCE_NAME, WEBSOCKET_ADDRESS, FLASK_ADDRESS


main = Blueprint('main', __name__)


@main.route("/", methods=['GET', 'POST'])
def handle_call():
    """Respond to incoming calls and start audio processing"""
    resp = VoiceResponse()

    logger.info("Starting call")

    dial = Dial()
    # Start the conference and set statusCallback to monitor participant events
    # assume that initially user is already calling someone else
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
    caller_number = params.get('From')
    print(params)
    logger.info(f"Conference Event: {event}, Caller: {caller_number}, CallSid: {participant_call_sid}")

    if event == 'participant-leave':
        if is_user_number(caller_number):
            logger.info("User has left the conference.")
            call_bot()
    elif event == 'participant-join':
        # if user is joining assume that they have already been in the confrence
        if is_user_number(caller_number):
            logger.info("User has joined the conference.")
            # If the bot is in the conference, remove it
            #remove_bot_from_conference()
        elif is_bot_number(caller_number):
            logger.info("Bot has joined the conference.")

    return '', 200

def call_bot():
    """Call the bot and have it join the conference"""
    call = twilio_client.calls.create(
        to=TWILIO_NUMBER,  # Bot's number (could be the same as your Twilio number)
        from_=TWILIO_NUMBER,
        url=FLASK_ADDRESS + '/bot_join_conference',
        method='POST'
    )
    return call


@main.route("/bot_join_conference", methods=['GET', 'POST'])
def bot_join_conference():
    response = VoiceResponse()

    # Start Media Stream to monitor audio
    start = Start()
    start.stream(
        name='BotMediaStream',
        url= f"wss://{WEBSOCKET_ADDRESS}/media"
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


@main.route("/user_rejoin_conference", methods=['GET', 'POST'])
def user_rejoin_conference():
    response = VoiceResponse()
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


def is_user_number(caller_number):
    # Normalize numbers if necessary
    return caller_number == TARGET_NUMBER


def is_bot_number(caller_number):
    # Replace with your bot's number if applicable
    return caller_number == TWILIO_NUMBER


@main.route("/test", methods=['GET'])
def test():
    """A simple test endpoint that returns 'Hello, World!'"""

    return "Hello, World!"