from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse, Gather, Dial, Start
import argparse
import dotenv
from speech_checker import is_hold_message
from utils import setup_logging, setup_twilio
import os
import requests
from datetime import datetime
# Load environment variables from the correct path
dotenv.load_dotenv('env/.env')

# Call the function to set up logging
logger = setup_logging()
twilio_client = setup_twilio()
TWILIO_NUMBER = '+12028164470'
TARGET_NUMBER = '+19164729906'
CONFERENCE_NAME = 'my_conference'
app = Flask(__name__)

@app.route("/", methods=['GET', 'POST'])
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


@app.route("/conference_events", methods=['POST'])
def conference_events():
    event = request.form.get('StatusCallbackEvent')
    participant_call_sid = request.form.get('CallSid')
    caller_number = request.form.get('Caller')
    logger.info(f"Conference Event: {event}, Caller: {caller_number}")

    if event == 'participant-join':
        if is_user_number(caller_number):
            logger.info("User has rejoined the conference.")
            # Instruct the bot to leave
            remove_bot_from_conference()
    return '', 200



@app.route("/gather_audio", methods=['POST'])
def gather_audio():
    """Handle the gather"""
    resp = VoiceResponse()
    resp.append(get_voice_gather())
    return str(resp)


@app.route("/process_audio", methods=['POST'])
def process_audio():
    """Process the audio collected from the call"""
    speech_result = request.form.get('SpeechResult')  
    response = VoiceResponse()

    if not speech_result:
        # no speech detected, continue gathering input
        gather = get_voice_gather()
        response.append(gather)
        return str(response)

    # got speech, process it
    logger.info("Processing audio" + speech_result)
    if is_hold_message(speech_result):
        user_left = True # fix 
        if user_left:
            # assuming that the user has already left the call
            call_instance = twilio_client.calls.create(
                to=TARGET_NUMBER,
                from_=TWILIO_NUMBER,
                url=FLASK_ADDRESS + '/merge_in_user',
                method='POST'
            )
            response.say("Connecting you back")  # unsure if it reaches here
        else:
            # call finish_call through api
            requests.post(FLASK_ADDRESS + '/finish_call')  # unsure if i need to capture a return value

    else:
        # got speech but wasn't human speech, continue gathering input
        gather = get_voice_gather()
        response.append(gather)

    return str(response)


@app.route("/bot_join_conference", methods=['GET', 'POST'])
def bot_join_conference():
    response = VoiceResponse()

    # Start Media Stream to monitor audio
    start = Start()
    start.stream(
        name='BotMediaStream',
        url='wss://your-server.com/media'  # Your WebSocket server for media streams
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


@app.route("/user_join_conference", methods=['GET', 'POST'])
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



@app.route("/merge_in_user", methods=['GET', 'POST'])
def merge_in_user():
    """TwiML to merge the user back into the conference"""
    response = VoiceResponse()
    logger.info("Merging user back into the conference")
    # Rejoin the user to the existing conference
    dial = Dial()
    dial.conference(
        'CONFERENCE_NAME',
        start_conference_on_enter=True,
        end_conference_on_exit=False,
        status_callback='/finish_call',
        #status_callback_event='join leave end',
        status_callback_event='join',
        status_callback_method='POST'
    )
    response.append(dial)

    return str(response)

@app.route("/finish_call", methods=['GET', 'POST'])
def finish_call(response):
    response = VoiceResponse()

    response.say("Exiting the call. Goodbye!")
    response.leave()

    return str(response)


def get_voice_gather():
    return Gather(input='speech', 
                  timeout=7, 
                  action='/process_audio', 
                  speech_timeout=7,
                  actionOnEmptyResult=True)


def call_bot():
    """Call the bot and have it join the conference"""
    call = twilio_client.calls.create(
        to=TWILIO_NUMBER,  # Bot's number (could be the same as your Twilio number)
        from_=TWILIO_NUMBER,
        url=FLASK_ADDRESS + '/bot_join_conference',
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


@app.route("/test", methods=['GET'])
def test():
    """A simple test endpoint that returns 'Hello, World!'"""

    return "Hello, World!"

def main():
    run_locally = True
    if run_locally:
        parser = argparse.ArgumentParser(description='Set ngrok forwarding addresses as environment variables.')
        parser.add_argument('forwarding_address_3000', type=str, help='Forwarding address for port 3000')
        args = parser.parse_args()

    # Save forwarding addresses as global variables
    global FLASK_ADDRESS
    FLASK_ADDRESS = args.forwarding_address_3000
    
    print("Forwarding addresses set as environment variables:")
    print(f"FLASK_ADDRESS: {FLASK_ADDRESS}")
    logger.info("Forwarding addresses set as environment variables:")
    logger.info(f"FLASK_ADDRESS: {FLASK_ADDRESS}")
    # Start the Flask app
    app.run(debug=True, port=3000)


if __name__ == "__main__":
    main()