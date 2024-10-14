from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse, Gather
import argparse
import dotenv
from speech_checker import is_human_speech
from utils import setup_logging, setup_twilio

# Load environment variables from the correct path
dotenv.load_dotenv('env/.env')

# Call the function to set up logging
logger = setup_logging()
twilio_client = setup_twilio()

app = Flask(__name__)

# This route handles the incoming call and streams the audio
@app.route("/", methods=['GET', 'POST'])
def voice():
    """Respond to incoming calls and start audio processing"""
    resp = VoiceResponse()
    logger.info("Starting call")
    gather = get_voice_gather()
    #gather.say("Will text when ready. Holding")
    resp.append(gather)

    return str(resp)

@app.route("/process_audio", methods=['POST'])
def process_audio():
    """Process the audio collected from the call"""
    speech_result = request.form.get('SpeechResult')  
    response = VoiceResponse()

    if speech_result:
        logger.info("Processing audio" + speech_result)
        if is_human_speech(speech_result):
            response = complete_call(response)
        else:
            # Continue gathering input
            gather = get_voice_gather()
            response.append(gather)

    else:
        gather = get_voice_gather()
        response.append(gather)

    return str(response)

def complete_call(response):
    """Complete the call"""

    response.say("Exiting the call. Goodbye!")
    response.hangup()
    return str(response)

def call_user_back(response):
    """Call the user back"""
    response.say("Calling you back. Please wait.")
    response.dial(FLASK_ADDRESS)
    return str(response)


def send_alert(message):
    """Send a text alert"""
    twilio_client.messages.create(
        body=message,
        from_=TWILIO_NUMBER,
        to=TARGET_NUMBER
    )

def get_voice_gather():
    return Gather(input='speech', 
                  timeout=7, 
                  action='/process_audio', 
                  actionOnEmptyResult=True)

def flush_logger():
    logger.handlers.clear() 

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
    
    global TWILIO_NUMBER, TARGET_NUMBER
    TWILIO_NUMBER = '+12028164470'
    TARGET_NUMBER = '+19164729906'

    print("Forwarding addresses set as environment variables:")
    print(f"FLASK_ADDRESS: {FLASK_ADDRESS}")
    logger.info("Forwarding addresses set as environment variables:")
    logger.info(f"FLASK_ADDRESS: {FLASK_ADDRESS}")
    # Start the Flask app
    app.run(debug=True, port=3000)

if __name__ == "__main__":
    main()