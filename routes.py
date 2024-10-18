from flask import request, Blueprint, g
from twilio.twiml.voice_response import VoiceResponse, Gather, Dial, Start
import dotenv
from speech_checker import is_hold_message
from utils import logger, twilio_client
import requests
from datetime import datetime
from constants import TWILIO_NUMBER, TARGET_NUMBER, CONFERENCE_NAME


# Load environment variables from the correct path
dotenv.load_dotenv('env/.env')

main = Blueprint('main', __name__)


@main.route("/", methods=['GET', 'POST'])
def handle_call():
    """Respond to incoming calls and start audio processing"""
    resp = VoiceResponse()

    logger.info("Starting call")

    dial = Dial()
    # Start the conference and set statusCallback to monitor participant events
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
    event = request.form.get('StatusCallbackEvent')
    participant_call_sid = request.form.get('CallSid')
    caller_number = request.form.get('Caller')
    logger.info(f"Conference Event: {event}, Caller: {caller_number}")

    if event == 'participant-leave':
        if is_user_number(caller_number):
            logger.info("User has left the conference.")
            # Call the bot to join and monitor
            call_bot()
    elif event == 'participant-join':
        if is_user_number(caller_number):
            logger.info("User has joined the conference.")
            # If the bot is in the conference, remove it
            remove_bot_from_conference()
    return '', 200

@main.route("/bot_join_conference", methods=['GET', 'POST'])
def bot_join_conference():
    response = VoiceResponse()

    # Start Media Stream to monitor audio
    start = Start()
    start.stream(
        name='BotMediaStream',
        url='wss://your-server.com/media'  # SETUP the websocket server 
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


@main.route("/user_join_conference", methods=['GET', 'POST'])
def user_join_conference():
    response = VoiceResponse()
    dial = Dial()
    dial.conference(
        CONFERENCE_NAME,
        start_conference_on_enter=True,
        end_conference_on_exit=False
    )
    response.append(dial)
    return str(response)


@main.route("/finish_call", methods=['GET', 'POST'])
def finish_call(response):
    response = VoiceResponse()

    response.say("Exiting the call. Goodbye!")
    response.leave()

    return str(response)

def call_bot():
    """Call the bot and have it join the conference"""
    call = twilio_client.calls.create(
        to=TWILIO_NUMBER,  # Bot's number (could be the same as your Twilio number)
        from_=TWILIO_NUMBER,
        url=g.FLASK_ADDRESS + '/bot_join_conference',
        method='POST'
    )
    return call

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