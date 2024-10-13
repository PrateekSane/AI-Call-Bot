from flask import Flask, request, jsonify
from twilio.twiml.voice_response import VoiceResponse, Start, Gather
from twilio.rest import Client
import os
import argparse
import dotenv
from speech_checker import is_human_speech, AudioSegment, io
import requests

# Load environment variables from the correct path
dotenv.load_dotenv('env/.env')

app = Flask(__name__)

# Twilio client setup
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')

# Check if environment variables are loaded correctly
if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
    raise ValueError("Twilio credentials not found in environment variables.")

twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# This route handles the incoming call and streams the audio
@app.route("/", methods=['GET', 'POST'])
def voice():
    """Respond to incoming calls and start audio processing"""
    resp = VoiceResponse()
    print("Starting call")
    gather = Gather(input="speech", timeout=5, action="/process_audio")
    gather.say("Will text when ready. Holding")
    resp.append(gather)

    return str(resp)

@app.route("/process_audio", methods=['POST'])
def process_audio():
    """Process the audio collected from the call"""
    speech_result = request.form.get('SpeechResult')    
    print("Processing audio")
    if "stop" in speech_result.lower():
        response = VoiceResponse()
        response.say("Ending the call. Goodbye!")
        response.hangup()
    else:
        # Continue gathering input
        response = VoiceResponse()
        gather = Gather(input='speech', action='/process_audio', speechTimeout='auto')
        gather.say("Please say something again.")
        response.append(gather)

    return str(response)
    """
    if not speech_result:
        return voice()  # Continue listening if no audio captured

    audio_content = requests.get(audio_url).content
    audio = AudioSegment.from_file(io.BytesIO(audio_content), format="wav")
    
    if is_human_speech(audio):
        send_end_hold_alert()
        return hangup()
    """
    return voice()  # Continue listening if not human speech

def hangup():
    """Hang up the call when speech is detected"""
    print("Hanging up the call")
    call_sid = request.json.get('call_sid')
    
    if call_sid:
        #send_end_hold_alert()
        twilio_client.calls(call_sid).update(status="completed")
        return jsonify({"message": "Call has been hung up."}), 200
    else:
        return jsonify({"error": "call_sid not provided."}), 400


def send_end_hold_alert():
    send_alert("Call has been hung up.")


def send_alert(message):
    """Send a text alert"""
    twilio_number = '+12028164470'
    target_number = '+19164729906'
    twilio_client.messages.create(
        body=message,
        from_=twilio_number,
        to=target_number
    )

def file_logger(message):
    """Write the provided message to a file named test.txt"""
    with open('test.txt', 'a') as file:
        file.write(message + '\n')

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

    # Start the Flask app
    app.run(debug=True, port=3000)
