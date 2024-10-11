from flask import Flask, request, jsonify
from twilio.twiml.voice_response import VoiceResponse, Start
from twilio.rest import Client
import os
import argparse
import dotenv

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
@app.route("/voice", methods=['GET', 'POST'])
def voice():
    """Respond to incoming calls and start media stream"""
    resp = VoiceResponse()

    call_sid = request.values.get('CallSid')

    # Start the media stream and send the audio to your WebSocket server
    start = Start()
    stream_addr = f"wss://{WEBSOCKET_ADDRESS}/stream?call_sid={call_sid}"
    start.stream(url=stream_addr)
    resp.append(start)

    # Message while monitoring
    resp.say("Monitoring hold. You will get a text when it's done.")

    return str(resp)


@app.route("/hangup", methods=['POST'])
def hangup():
    """Hang up the call when speech is detected"""
    call_sid = request.json.get('call_sid')
    
    if call_sid:
        send_end_hold_alert()
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