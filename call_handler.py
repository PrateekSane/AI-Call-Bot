from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse, Gather, Dial
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
    dial.conference(
        'CONFERENCE_NAME',
        start_conference_on_enter=True, # might be false
        end_conference_on_exit=False,
        status_callback='/gather_audio',
        #status_callback_event='join leave end',
        status_callback_event='join',
        status_callback_method='POST'
    )
    '''
    # Start the conference and set statusCallback to monitor participant events
    dial.conference(
        ,
        start_conference_on_enter=True,
        end_conference_on_exit=False,
        status_callback='/conference_events',
        status_callback_event='join leave',
        status_callback_method='POST'
    )
    resp.append(dial)
    '''

    return str(resp)

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


# @app.route("/wait", methods=['POST'])
# def make_customer_service_wait():
#     """Make the customer service wait"""
#     response = VoiceResponse()
#     response.say("Thank you for picking up. I am an assistant and will connect you shortly")
#     return str(response)


# def send_alert(message):
#     """Send a text alert"""
#     twilio_client.messages.create(
#         body=message,
#         from_=TWILIO_NUMBER,
#         to=TARGET_NUMBER
#     )

# @app.route('/recording_callback', methods=['POST'])
# def recording_callback():
#     """Receive recording status and download the recording"""
#     recording_url = request.form.get('RecordingUrl')
#     recording_sid = request.form.get('RecordingSid')

#     if recording_url:
#         logger.info(f"Recording URL received: {recording_url}")

#         # Construct the local file name
#         timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#         local_filename = os.path.join("/recordings", f"{timestamp}_{recording_sid}.wav")

#         # Download the recording
#         response = requests.get(recording_url + '.wav')
#         if response.status_code == 200:
#             with open(local_filename, 'wb') as f:
#                 f.write(response.content)
#             logger.info(f"Recording saved locally as: {local_filename}")
#         else:
#             logger.error(f"Failed to download recording: {response.status_code}")

#     return '', 200

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