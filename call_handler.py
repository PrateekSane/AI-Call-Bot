from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse, Gather, Dial
import argparse
import dotenv
from speech_checker import is_human_speech
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

app = Flask(__name__)

@app.route("/", methods=['GET', 'POST'])
def voice():
    """Respond to incoming calls and start audio processing"""
    resp = VoiceResponse()
    logger.info("Starting call")
    
    # Start with a <Dial> verb
    conference_dial = get_conference_dial(TARGET_NUMBER)

    resp.append(get_voice_gather())
    resp.append(conference_dial)

    return str(resp)

@app.route("/process_audio", methods=['POST'])
def process_audio():
    """Process the audio collected from the call"""
    speech_result = request.form.get('SpeechResult')  
    response = VoiceResponse()
    if speech_result:
        logger.info("Processing audio" + speech_result)
        if is_human_speech(speech_result):
            logger.info("Human speech detected" + str(response))
            response = complete_call(response)
            logger.info("Human speech detected" + str(response))
        else:
            # Continue gathering input
            gather = get_voice_gather()
            response.append(gather)

    else:
        gather = get_voice_gather()
        response.append(gather)

    return str(response)

@app.route("/merge_in_user", methods=['GET', 'POST'])
def merge_in_user():
    """TwiML to merge the user back into the conference"""
    response = VoiceResponse()
    logger.info("Merging user back into the conference")
    # Rejoin the user to the existing conference
    dial = get_conference_dial(TARGET_NUMBER)
    response.append(dial)

    response.pause(5)

    response.say("Exiting the call. Goodbye!")
    response.leave()

    return str(response)


def complete_call(response):
    """Complete the call"""
    logger.info("Completing call")
    call_instance = call_user_back()

    return str(response)

def call_user_back():
    """Call the user back"""
    call_instance = twilio_client.calls.create(
        to=TARGET_NUMBER,
        from_=TWILIO_NUMBER,
        url=FLASK_ADDRESS + '/merge_in_user',
        method='POST'
    )
    return call_instance


def get_voice_gather():
    return Gather(input='speech', 
                  timeout=7, 
                  action='/process_audio', 
                  speech_timeout=7,
                  actionOnEmptyResult=True)

def get_conference_dial(from_number):
    dial = Dial()
    if from_number == TARGET_NUMBER:
        dial.conference(
            'InitialConference',
            start_conference_on_enter=False,
            end_conference_on_exit=False)
    else:
        # Otherwise have the caller join as a regular participant
        dial.conference(
            'FinalConference',
            start_conference_on_enter=True,
            end_conference_on_exit=False)

    return dial 


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