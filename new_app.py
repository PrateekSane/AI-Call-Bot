import os
import json
import base64
import asyncio
import websockets
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.websockets import WebSocketDisconnect
from twilio.twiml.voice_response import VoiceResponse, Connect, Say, Stream
from dotenv import load_dotenv
from twilio.rest import Client
from twilio.twiml.voice_response import Dial
from constants import CUSTOMER_SERVICE_NUMBER, TWILIO_PHONE_NUMBER, CONFERENCE_NAME
import logging
import random

load_dotenv('env/.env')


# Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY') # requires OpenAI Realtime API Access
if not OPENAI_API_KEY:
    raise ValueError('Missing the OpenAI API key. Please set it in the .env file.')

PORT = int(os.getenv('PORT', 5050))
twilio_client = Client(os.getenv('TWILIO_ACCOUNT_SID'), os.getenv('TWILIO_AUTH_TOKEN'))

user_name = "John Doe"
user_email = "john.doe@example.com"
user_phone_number = "+19164729906"
reason_for_call = "I need help with my account"

SYSTEM_PROMPT = f"""You are the {user_name}'s helpful assistant and you are calling on their behalf to a customer service agent. YOU ARE NOT {user_name}.
    You are given the following pieces of information about the {user_name}. Use this information to help the customer service agent. Keep your responses concise and to the point.
    User Name: {user_name} 
    User Email: {user_email} 
    User Phone Number: {user_phone_number} 
    Reason for call: {reason_for_call} 
    You need to give the customer service agent the best possible information about the user so that they can help them. 
    When you get stuck or you have given the customer service agent all the information you can, say "I need to redirect you to a human agent". 
    Do not make up information."""

print(SYSTEM_PROMPT)

VOICE = 'alloy'

LOG_EVENT_TYPES = [
    'response.content.done', 'rate_limits.updated', 'response.done',
    'input_audio_buffer.committed', 'input_audio_buffer.speech_stopped',
    'input_audio_buffer.speech_started', 'session.created'
]
app = FastAPI()


@app.get("/", response_class=JSONResponse)
async def index_page():
    return {"message": "Twilio Media Stream Server is running!"}

@app.api_route("/initiate-call", methods=["GET"])
async def initiate_call(request: Request):
    host = request.url.hostname
    call = twilio_client.calls.create(
        to=CUSTOMER_SERVICE_NUMBER,
        from_=TWILIO_PHONE_NUMBER,
        url=f"https://{host}/incoming-call",
        status_callback=f"https://{host}/call_events",
        status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
        status_callback_method='POST'
    )
    return {"message": "Call initiated"}


@app.api_route("/incoming-call", methods=["GET", "POST"])
async def incoming_call(request: Request):
    """Handle incoming call and return TwiML response to connect to Media Stream."""
    response = VoiceResponse()
    # <Say> punctuation to improve text-to-speech flow
    response.pause(length=1)
    response.say("O.K. you can start talking!")
    host = request.url.hostname
    connect = Connect()
    connect.stream(url=f'wss://{host}/media-stream')
    response.append(connect)

    # Add the caller to the conference
    dial = Dial()
    dial.conference(
        CONFERENCE_NAME,
        start_conference_on_enter=True,
        end_conference_on_exit=False,
        status_callback=f"https://{host}/conference_events",
        status_callback_event=['start', 'end', 'join', 'leave'],
        status_callback_method='POST',
    )
    response.append(dial)
    
    return HTMLResponse(content=str(response), media_type="application/xml")


@app.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    """Handle WebSocket connections between Twilio and OpenAI."""
    print("Client connected")
    host = websocket.url.hostname
    await websocket.accept()
    async with websockets.connect(
        'wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01',
        extra_headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "OpenAI-Beta": "realtime=v1"
        }
    ) as openai_ws:
        await send_session_update(openai_ws)
        stream_sid = None
        async def receive_from_twilio():
            """Receive audio data from Twilio and send it to the OpenAI Realtime API."""
            nonlocal stream_sid
            try:
                async for message in websocket.iter_text():
                    data = json.loads(message)
                    if data['event'] == 'media' and openai_ws.open:
                        audio_append = {
                            "type": "input_audio_buffer.append",
                            "audio": data['media']['payload']
                        }
                        await openai_ws.send(json.dumps(audio_append))
                    elif data['event'] == 'start':
                        stream_sid = data['start']['streamSid']
                        print(f"Incoming stream has started {stream_sid}")
            except WebSocketDisconnect:
                print("Client disconnected.")
                if openai_ws.open:
                    await openai_ws.close()
        async def send_to_twilio():
            """Receive events from the OpenAI Realtime API, send audio back to Twilio."""
            nonlocal stream_sid
            try:
                async for openai_message in openai_ws:
                    response = json.loads(openai_message)
                    if response['type'] in LOG_EVENT_TYPES:
                        print(f"Received event: {response['type']}", response)

                    if response['type'] == 'session.updated':
                        print("Session updated successfully:", response)


                    if response['type'] == 'response.audio.delta' and response.get('delta'):
                        # Audio from OpenAI
                        try:
                            audio_payload = base64.b64encode(base64.b64decode(response['delta'])).decode('utf-8')
                            audio_delta = {
                                "event": "media",
                                "streamSid": stream_sid,
                                "media": {
                                    "payload": audio_payload
                                }
                            }
                            await websocket.send_json(audio_delta)
                        except Exception as e:
                            print(f"Error processing audio data: {e}")

                    if response['type'] == 'response.done':
                        if 'response' in response:
                            if is_bot_redirect(response['response']['output'][0]['content'][0]['transcript']):
                                dial_user(host)
            except Exception as e:
                print(f"Error in send_to_twilio: {e}")
        await asyncio.gather(receive_from_twilio(), send_to_twilio())

async def send_session_update(openai_ws):
    """Send session update to OpenAI WebSocket."""
    session_update = {
        "type": "session.update",
        "session": {
            "turn_detection": {"type": "server_vad"},
            "input_audio_format": "g711_ulaw",
            "output_audio_format": "g711_ulaw",
            "voice": VOICE,
            "instructions": SYSTEM_PROMPT,
            "modalities": ["text", "audio"],
            "temperature": 0.8,
        }
    }
    print('Sending session update:', json.dumps(session_update))
    await openai_ws.send(json.dumps(session_update))


def is_bot_redirect(transcript):
    """Check if the word 'redirect' exists in the transcript"""
    transcript_words = transcript.split()
    is_redirect = 'redirect' in transcript_words
    print(f"Is redirect: {is_redirect}")
    return is_redirect

def dial_user(call_url):
    """Dial the user number when redirect is detected"""
    try:
        # Initialize the Twilio client
        print("CALLING BACK USER") 
        # Make the call

        call = twilio_client.calls.create(
            to=user_phone_number,
            from_=TWILIO_PHONE_NUMBER,
            url=f"https://{call_url}/handle_user_call",
            # status_callback=f"https://{call_url}/call_events",
            # status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
            # status_callback_method='POST'
        )
        print(f"Initiated call to user with SID: {call.sid}")
        return call.sid
    except Exception as e:
        print(f"Error initiating call to user: {e}")
        return None
    
@app.api_route("/call_events", methods=["POST"])
def call_events(request: Request):
    """Handle call events"""
    params = request.form()
    # call_sid = params.get('CallSid')
    # call_status = params.get('CallStatus')
    # print(f"Call {call_status} for CallSid: {call_sid}")
    # Handle events based on call status if necessary
    return '', 200


@app.api_route("/handle_user_call", methods=['POST'])
def handle_user_call(request: Request):
    """Handle incoming calls and create a conference"""
    response = VoiceResponse()
    
    # Get the caller information
    # caller_sid = request.values.get('CallSid')
    # user_call_sid = caller_sid
    host = request.url.hostname
    
    # Add the caller to the conference
    dial = Dial()
    dial.conference(
        CONFERENCE_NAME,
        start_conference_on_enter=False,
        end_conference_on_exit=True,
        status_callback=f"https://{host}/conference_events",
        status_callback_event=['start', 'end', 'join', 'leave'],
        status_callback_method='POST',
    )
    response.append(dial)

    return HTMLResponse(content=str(response), media_type="application/xml")

@app.api_route("/conference_events", methods=['POST'])
def conference_events(request: Request):
    """Handle conference status events"""
    try:
        event_type = request.values.get('StatusCallbackEvent')
        conference_sid = request.values.get('ConferenceSid')
        call_sid = request.values.get('CallSid')
        
        print(f"Conference Event: {event_type} for conference {conference_sid}")
        
        """
        if event_type == 'participant-join':
            # Check if this is the user joining (you'll need to track the user's CallSid)
            if call_sid == user_call_sid:  # You'll need to store user_call_sid when making the initial call
                # Connect the bot to the conference
                connect_bot_to_conference(conference_sid)
                
        elif event_type == 'participant-leave':
            reason = request.values.get('ReasonParticipantLeft', 'unknown')
            logger.info(f"Participant left conference. Reason: {reason}")
            
            # If the bot is in the conference and the user has joined, remove the bot
            if is_user_connected(conference_sid) and is_bot_connected(conference_sid):
                remove_bot_from_conference(conference_sid)
        """
        return '', 200
        
    except Exception as e:
        print(f"Error handling conference event: {e}")
        return str(e), 500
        

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
