from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse, Start
from twilio.rest import Client
import os
from json import jsonify
import argparse

app = Flask(__name__)

# Twilio client setup
TWILIO_ACCOUNT_SID = os.environ['TWILIO_ACCOUNT_SID']
TWILIO_AUTH_TOKEN = os.environ['TWILIO_AUTH_TOKEN']
WEBSOCKET_ADDRESS = os.environ['WEBSOCKET_ADDRESS']

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
        send_hangup_alert()
        twilio_client.calls(call_sid).update(status="completed")
        return jsonify({"message": "Call has been hung up."}), 200
    else:
        return jsonify({"error": "call_sid not provided."}), 400


def send_hangup_alert():
    send_alert("Call has been hung up.")


def send_alert(message):
    """Send a text alert"""
    twilio_client.messages.create(
        body=message,
        from_=os.environ['TWILIO_PHONE_NUMBER'],
        to=os.environ['ALERT_PHONE_NUMBER']
    )


@app.route("/test", methods=['GET'])
def test():
    """A simple test endpoint that returns 'Hello, World!'"""
    return "Hello, World!"

if __name__ == "__main__":
    # Set up argument parsing
    parser = argparse.ArgumentParser(description='Set ngrok forwarding addresses as environment variables.')
    parser.add_argument('forwarding_address_3000', type=str, help='Forwarding address for port 3000')
    parser.add_argument('forwarding_address_8765', type=str, help='Forwarding address for port 8765')
    
    args = parser.parse_args()

    # Save forwarding addresses as environment variables
    os.environ['FLASK_ADDRESS'] = args.forwarding_address_3000
    os.environ['WEBSOCKET_ADDRESS'] = args.forwarding_address_8765

    print("Forwarding addresses set as environment variables:")
    print(f"FORWARDING_ADDRESS_8765: {os.environ['FORWARDING_ADDRESS_8765']}")
    print(f"FORWARDING_ADDRESS_3000: {os.environ['FORWARDING_ADDRESS_3000']}")

    # Start the Flask app
    app.run(debug=True, port=3000)