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
from utils import twilio_client, logger
from prompts import user_name, user_phone_number
from openai_utils import get_openai_response
from deepgram_handler import create_deepgram_stt_connection, close_deepgram_stt_connection, convert_mp3_to_mulaw, synthesize_speech

load_dotenv('env/.env')

active_calls = twilio_client.calls.list(
    from_=TWILIO_PHONE_NUMBER,
    status="in-progress"
)
bot_call_sid = None
user_call_sid = None

# End each active call by updating its status to 'completed'
for call in active_calls:
    twilio_client.calls(call.sid).update(status="completed")
    print(f"Ended call with SID: {call.sid}")


PORT = int(os.getenv('PORT', 5050))
twilio_client = Client(os.getenv('TWILIO_ACCOUNT_SID'), os.getenv('TWILIO_AUTH_TOKEN'))

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

@app.api_route("/initiate-call", methods=["GET", "POST"])
async def initiate_call(request: Request):
    host = request.url.hostname

    # This triggers the webhook to the bot which makes it start the stream
    bot_call = twilio_client.calls.create(
        to=TWILIO_PHONE_NUMBER,
        from_=TWILIO_PHONE_NUMBER,
        url=f"https://{host}/bot_join_conference",
        status_callback=f"https://{host}/call_events",
        status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
        status_callback_method='POST'
    )
    global bot_call_sid
    bot_call_sid = bot_call.sid
    customer_service_call = twilio_client.calls.create(
        to=CUSTOMER_SERVICE_NUMBER,
        from_=TWILIO_PHONE_NUMBER,
        url=f"https://{host}/cs_join_conference",
        status_callback=f"https://{host}/call_events",
        status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
        status_callback_method='POST'
    )
    cs_call_sid = customer_service_call.sid
    return {"message": "Calls initiated"}


@app.api_route("/bot_join_conference", methods=["GET", "POST"])
async def bot_join_conference(request: Request):
    """Handle incoming call and return TwiML response to connect to Media Stream."""
    response = VoiceResponse()
    host = request.url.hostname

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

@app.api_route("/cs_join_conference", methods=["GET", "POST"])
async def cs_join_conference(request: Request):
    """Handle incoming call and return TwiML response to connect to Media Stream."""
    response = VoiceResponse()
    host = request.url.hostname

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


# Called from the webhook on twilio
@app.api_route("/incoming-call", methods=["GET", "POST"])
async def incoming_call(request: Request):
    """Handle incoming call and return TwiML response to connect to Media Stream."""
    response = VoiceResponse()
    # <Say> punctuation to improve text-to-speech flow
    response.pause(length=1)
    response.say(f"Hi, Im an helpful agent working for {user_name}")
    host = request.url.hostname

    connect = Connect()
    connect.stream(url=f'wss://{host}/media-stream')
    response.append(connect)

    return HTMLResponse(content=str(response), media_type="application/xml")

@app.websocket("/media-stream")
async def handle_media_stream(twilio_websocket: WebSocket):
    """
    1. Accept the Twilio WebSocket.
    2. Create a Deepgram STT connection.
    3. On each transcript from Deepgram, call GPT -> TTS -> Twilio.
    4. If GPT says "redirect", call dial_user.
    """
    logger.info("Twilio WebSocket connected.")
    await twilio_websocket.accept()

    # We'll store the streamSid Twilio sends so we can route our TTS back to Twilio
    twilio_stream_sid = None

    # -- ASYNC callback for Deepgram transcripts -- #
    async def on_transcript(transcript: str):
        logger.info(f"[STT Transcript] {transcript}")
        """
        gpt_reply = await get_openai_response(transcript)
        logger.info(f"[GPT Response] {gpt_reply}")

        # Check for 'redirect'
        if is_redirect(gpt_reply):
            call_url = twilio_websocket.url.hostname
            dial_user(call_url)
            # TODO: have it say that redirecting the call to the user
            return

        # 3) Synthesize GPT text with Deepgram TTS
        tts_mp3 = await synthesize_speech(gpt_reply)
        if not tts_mp3:
            return

        # 4) Convert MP3 -> mu-law 8kHz
        tts_mulaw = convert_mp3_to_mulaw(tts_mp3)
        if not tts_mulaw:
            return

        # 5) Base64-encode & send back to Twilio
        if twilio_stream_sid:
            payload_b64 = base64.b64encode(tts_mulaw).decode("utf-8")
            media_msg = {
                "event": "media",
                "streamSid": twilio_stream_sid,
                "media": {"payload": payload_b64},
            }
            await twilio_websocket.send_json(media_msg)
            logger.info("Sent TTS audio back to Twilio.")
        """

    # Create Deepgram STT connection
    dg_connection = await create_deepgram_stt_connection(on_transcript)
    if dg_connection is None:
        logger.error("Failed to open Deepgram STT. Closing Twilio WS.")
        await twilio_websocket.close()
        return

    try:
        while True:
            message_text = await twilio_websocket.receive_text()
            data = json.loads(message_text)

            event_type = data.get("event", "")
            if event_type == "start":
                twilio_stream_sid = data["start"]["streamSid"]
                logger.info(f"Twilio stream started: {twilio_stream_sid}")

            elif event_type == "media":
                # STT inbound from user
                audio_b64 = data["media"]["payload"]
                audio_bytes = base64.b64decode(audio_b64)
                dg_connection.send(audio_bytes)

            elif event_type == "stop":
                logger.info("Received Twilio 'stop' event. Ending stream.")
                break

    except WebSocketDisconnect:
        logger.info("Twilio WS disconnected unexpectedly.")
    except Exception as e:
        logger.error(f"Error reading Twilio WS: {e}")
    finally:
        await close_deepgram_stt_connection(dg_connection)
        await twilio_websocket.close()
        logger.info("Closed Twilio WS and Deepgram STT connection.")


def is_bot_redirect(transcript):
    """Check if the word 'redirect' exists in the transcript"""
    transcript_words = transcript.split()
    transcript_words = [word.lower() for word in transcript_words]
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
        user_call_sid = call.sid
        print(f"Initiated call to user with SID: {call.sid}")
        return call.sid
    except Exception as e:
        print(f"Error initiating call to user: {e}")
        return None
    
@app.api_route("/call_events", methods=["POST"])
def call_events(request: Request):
    """Handle call events"""
    
    return '', 200

@app.api_route("/user_call_events", methods=['POST'])
async def user_call_events(request: Request):
    """Handle user call events"""
    form_data = await request.form()
    call_status = form_data.get('CallStatus')
    print(f"User call event: {call_status} for CallSid")

    # Check if the user's call is in-progress (answered)
    if call_status == 'in-progress':
        # Remove the bot from the conference
        print(f"Removing bot from conference with SID: {bot_call_sid}")
        #
    return '', 200

@app.api_route("/handle_user_call", methods=['POST'])
def handle_user_call(request: Request):
    """Handle incoming calls and create a conference"""
    response = VoiceResponse()
    response.say(f"Connecting you with {user_name} now. Thank you!")
    print(f"ENDING CALL FROM THE BOT WITH SID")
    res = twilio_client.calls(bot_call_sid).update(status="completed") 
    print(f"ENDING CALL FROM THE BOT WITH SID: {res}")
    
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
