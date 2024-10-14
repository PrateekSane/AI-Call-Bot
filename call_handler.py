from flask import Flask, request, jsonify
from twilio.twiml.voice_response import VoiceResponse, Start, Gather
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
            response.say("Ending the call. Goodbye!")
            response.hangup()
        else:
            # Continue gathering input
            gather = get_voice_gather()
            logger.info("Please say something again.")
            response.append(gather)

    else:
        logger.info("No speech detected")
        gather = get_voice_gather()
        response.append(gather)

    return str(response)


def send_alert(message):
    """Send a text alert"""
    twilio_number = '+12028164470'
    target_number = '+19164729906'
    twilio_client.messages.create(
        body=message,
        from_=twilio_number,
        to=target_number
    )

def get_voice_gather():
    return Gather(input='speech', timeout=3, action='/process_audio', speech_timeout='auto', actionOnEmptyResult=True)

def flush_logger():
    logger.handlers.clear() 

@app.route("/test", methods=['GET'])
def test():
    """A simple test endpoint that returns 'Hello, World!'"""

    return "Hello, World!"

if __name__ == "__main__":
    # Set up argument parsing
    run_locally = True
    if run_locally:
        parser = argparse.ArgumentParser(description='Set ngrok forwarding addresses as environment variables.')
        parser.add_argument('forwarding_address_3000', type=str, help='Forwarding address for port 3000')
        parser.add_argument('forwarding_address_8765', type=str, help='Forwarding address for port 8765')
        
        args = parser.parse_args()

    # Save forwarding addresses as global variables
    global FLASK_ADDRESS, WEBSOCKET_ADDRESS
    FLASK_ADDRESS = args.forwarding_address_3000
    WEBSOCKET_ADDRESS = args.forwarding_address_8765

    print("Forwarding addresses set as environment variables:")
    print(f"FLASK_ADDRESS: {FLASK_ADDRESS}")
    print(f"WEBSOCKET_ADDRESS: {WEBSOCKET_ADDRESS}")
    logger.info("Forwarding addresses set as environment variables:")
    logger.info(f"FLASK_ADDRESS: {FLASK_ADDRESS}")
    logger.info(f"WEBSOCKET_ADDRESS: {WEBSOCKET_ADDRESS}")  
    # Start the Flask app
    app.run(debug=True, port=3000)
