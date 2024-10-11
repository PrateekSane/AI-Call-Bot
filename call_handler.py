from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse, Start
from twilio.rest import Client
import os
from json import jsonify

app = Flask(__name__)

# Twilio client setup
account_sid = os.environ['TWILIO_ACCOUNT_SID']
auth_token = os.environ['TWILIO_AUTH_TOKEN']
client = Client(account_sid, auth_token)

# This route handles the incoming call and streams the audio
@app.route("/voice", methods=['GET', 'POST'])
def voice():
    """Respond to incoming calls and start media stream"""
    resp = VoiceResponse()

    call_sid = request.values.get('CallSid')

    # Start the media stream and send the audio to your WebSocket server
    start = Start()
    start.stream(url=f"wss://your-server-url/stream?call_sid={call_sid}") 
    resp.append(start)

    # Message while monitoring
    resp.say("Monitoring hold. You will get a text when it's done.")

    return str(resp)

@app.route("/hangup", methods=['POST'])
def hangup():
    """Hang up the call when speech is detected"""
    # Assuming you have the call_sid stored somewhere
    call_sid = request.json.get('call_sid')
    
    if call_sid:
        # Use Twilio's REST API to hang up the call
        client.calls(call_sid).update(status="completed")
        return jsonify({"message": "Call has been hung up."}), 200
    else:
        return jsonify({"error": "call_sid not provided."}), 400

def send_alert(message):
    """Send a text alert"""
    client.messages.create(
        body=message,
        from_=os.environ['TWILIO_PHONE_NUMBER'],
        to=os.environ['ALERT_PHONE_NUMBER']
    )

@app.route("/test", methods=['GET'])
def test():
    """A simple test endpoint that returns 'Hello, World!'"""
    return "Hello, World!"

if __name__ == "__main__":
    app.run(debug=True, port=3000)