import base64
import json
import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.websockets import WebSocketDisconnect
from twilio.rest import Client
from twilio.twiml.voice_response import Connect, Say, Stream, VoiceResponse
from twilio_utils import create_call, create_conference, is_redirect, end_call

from constants import CallInfo
from call_manager import call_manager
from deepgram_handler import (
    close_deepgram_stt_connection,
    convert_mp3_to_mulaw,
    create_deepgram_stt_connection,
    synthesize_speech
)
from openai_utils import get_openai_response
from prompts import user_name
from utils import logger, twilio_client

load_dotenv('env/.env')

"""
# TODO: move into call_manager
active_calls = twilio_client.calls.list(
    from_=TWILIO_PHONE_NUMBER,
    status="in-progress"
)

# End each active call by updating its status to 'completed'
for call in active_calls:
    twilio_client.calls(call.sid).update(status="completed")
    print(f"Ended call with SID: {call.sid}")
"""


PORT = int(os.getenv('PORT', 5050))
app = FastAPI()


@app.get("/", response_class=JSONResponse)
async def index_page():
    return {"message": "Twilio Media Stream Server is running!"}


@app.api_route("/initiate-call", methods=["GET", "POST"])
async def initiate_call(request: Request):
    try:
        # Get JSON data from request
        data = await request.json()
        bot_number = data.get("bot_number")
        cs_number = data.get("cs_number")
        target_number = data.get("target_number")
        system_info = data.get("system_info", {})  # Additional fields for system prompt
        
        if not all([bot_number, cs_number, target_number]):
            return JSONResponse(
                status_code=400,
                content={"error": "Missing required fields"}
            )

        host = request.url.hostname
        session_id = call_manager.create_new_session()
        
        # Store all the call information in the session
        call_manager.set_session_value(session_id, "bot_number", bot_number)
        call_manager.set_session_value(session_id, "cs_number", cs_number)
        call_manager.set_session_value(session_id, "target_number", target_number)
        call_manager.set_session_value(session_id, "system_info", system_info)

        join_conference_url = f"https://{host}/caller_join_conference/{session_id}"
        call_events_url = f"https://{host}/call_events"
        
        # Rest of your existing call creation code...
        bot_call = create_call(
            twilio_client, 
            to=bot_number,
            from_=bot_number,
            url=join_conference_url,
            status_callback=call_events_url
        )
        call_manager.link_call_to_session(bot_call.sid, session_id)
        call_manager.set_session_value(session_id, CallInfo.OUTBOUND_BOT_SID, bot_call.sid)

        # Create customer service call...
        cs_call = create_call(
            twilio_client,
            to=cs_number,
            from_=bot_number,
            url=join_conference_url,
            status_callback=call_events_url
        )
        call_manager.link_call_to_session(cs_call.sid, session_id)
        call_manager.set_session_value(session_id, CallInfo.CUSTOMER_SERVICE_SID, cs_call.sid)
        
        return {"message": "Calls initiated", "session_id": session_id}
        
    except Exception as e:
        logger.error(f"Error initiating call: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@app.api_route("/caller_join_conference/{session_id}", methods=["GET", "POST"])
async def caller_join_conference(request: Request, session_id: str):
    """Handle incoming call and return TwiML response to connect to Media Stream."""
    response = VoiceResponse()
    host = request.url.hostname
    conference_name = call_manager.get_conference_name(session_id)

    # Add the caller to the conference
    conference_events_url = f"https://{host}/conference_events/{session_id}"
    response.append(create_conference(conference_name, host, conference_events_url))
    
    return HTMLResponse(content=str(response), media_type="application/xml")

# Called from the webhook on twilio
@app.api_route("/incoming-call", methods=["GET", "POST"])
async def incoming_call(request: Request):
    """Handle incoming call and return TwiML response to connect to Media Stream."""
    host = request.url.hostname
    form_data = await request.form()
    print("FORM DATA", form_data)
    print("QUERY PARAMS", request.query_params)
    incoming_call_sid = form_data.get('CallSid')
    # PROBLEM IS THAT INCOMING_CALL_SID IS NOT IN CALL MANAGER
    call_manager.link_call_to_session(incoming_call_sid, session_id)
    call_manager.set_session_value(session_id, CallInfo.INBOUND_BOT_SID, incoming_call_sid)

    response = VoiceResponse()
    response.pause(length=1)
    response.say(f"Hi, Im an helpful agent working for {user_name}")


    connect = Connect()
    connect.stream(url=f'wss://{host}/media-stream/{session_id}')
    response.append(connect)

    return HTMLResponse(content=str(response), media_type="application/xml")

@app.websocket("/media-stream/{session_id}")
async def handle_media_stream(twilio_websocket: WebSocket, session_id: str):
    """
    1. Accept the Twilio WebSocket.
    2. Create a Deepgram STT connection.
    3. On each transcript from Deepgram, call GPT -> TTS -> Twilio.
    4. If GPT says "redirect", call dial_user.
    """
    logger.info("Twilio WebSocket connected.")
    session_info = call_manager.get_session_by_id(session_id)
    if not session_info:
        logger.error(f"Session not found for CallSid: {session_id}. BE CAREFUL")

    await twilio_websocket.accept()

    # We'll store the streamSid Twilio sends so we can route our TTS back to Twilio
    twilio_stream_sid = None

    async def on_transcript(transcript: str):
        logger.info(f"[STT Transcript] {transcript}")

        # Get system info and generate prompt
        session_info = call_manager.get_session_by_id(session_id)
        system_info = session_info.get(CallInfo.SYSTEM_INFO.value, {}) if session_info else {}
        system_prompt = generate_system_prompt(system_info)
        
        # Get GPT response
        gpt_reply = get_openai_response(system_prompt, transcript)
        logger.info(f"[GPT Response] {gpt_reply}")

        # Check for 'redirect'
        if is_redirect(gpt_reply):
            call_url = twilio_websocket.url.hostname
            dial_user(call_url, session_id)
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
                call_manager.set_session_value(session_id, CallInfo.TWILIO_STREAM_SID, twilio_stream_sid)

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


def dial_user(call_url, session_id):
    """Dial the user number when redirect is detected"""
    try:
        call = create_call(
            twilio_client,
            to=user_phone_number,
            from_=TWILIO_PHONE_NUMBER,
            url=f"https://{call_url}/handle_user_call",
            status_callback=f"https://{call_url}/call_events",
            status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
            status_callback_method='POST'
        )
        call_manager.set_session_value(session_id, CallInfo.USER_SID, call.sid)

        print(f"Initiated call to user with SID: {call.sid}")
        return call.sid
    except Exception as e:
        print(f"Error initiating call to user: {e}")
        return None

@app.api_route("/handle_user_call", methods=['POST'])
async def handle_user_call(request: Request):
    """Handle incoming calls and create a conference"""
    host = request.url.hostname
    form_data = await request.form()
    session_id = form_data.get('CallSid')

    response = VoiceResponse()
    response.say(f"Connecting you with {user_name} now. Thank you!")

    session_info = call_manager.get_session_by_id(session_id)
    bot_call_sid = session_info.get(CallInfo.BOT_SID)
    end_call(twilio_client, bot_call_sid)
    
    # Add the caller to the conference
    response.append(
        create_conference(
            conference_name=call_manager.get_conference_name(session_id),
            call_events_url=f"https://{host}/conference_events/{session_id}",
            start_conference_on_enter=False,
            end_conference_on_exit=True
        )
    )

    return HTMLResponse(content=str(response), media_type="application/xml")

@app.api_route("/conference_events/{session_id}", methods=['POST'])
async def conference_events(request: Request, session_id: str):
    """Handle conference status events"""
    try:
        form_data = await request.form()
        event_type = form_data.get('StatusCallbackEvent')
        conference_sid = form_data.get('ConferenceSid')
        call_sid = form_data.get('CallSid')

        session_info = call_manager.get_session_by_id(session_id)
        call_manager.set_session_value(session_info, CallInfo.CONFERENCE_SID, conference_sid)
        
        print(f"Conference Event: {event_type} for conference {conference_sid}")
        
        if event_type == 'participant-join':
            # Check if this is the user joining (you'll need to track the user's CallSid)
            logger.debug(f"Conference join CallSid: {call_sid}")
            # if call_sid == user_call_sid:  # You'll need to store user_call_sid when making the initial call
            #     # Connect the bot to the conference
            #     connect_bot_to_conference(conference_sid)
                
        elif event_type == 'participant-leave':
            reason = form_data.get('ReasonParticipantLeft', 'unknown')
            logger.debug(f"Participant left conference. Reason: {reason}")
            
            # # If the bot is in the conference and the user has joined, remove the bot
            # if is_user_connected(conference_sid) and is_bot_connected(conference_sid):
            #     remove_bot_from_conference(conference_sid)
        return '', 200
        
    except Exception as e:
        print(f"Error handling conference event: {e}")
        return str(e), 500

        
@app.api_route("/call_events", methods=["POST"])
async def call_events(request: Request):
    """Handle call events"""
    try:
        form_data = await request.form()
        event_type = form_data.get('StatusCallbackEvent')
        call_sid = form_data.get('CallSid')
        parent_call_sid = form_data.get('ParentCallSid')
        conference_sid = form_data.get('ConferenceSid')

        logger.debug(f"Received call event: {event_type}")
        logger.debug(f"Call SID: {call_sid}")
        logger.debug(f"Parent Call SID: {parent_call_sid}")
        logger.debug(f"Conference SID: {conference_sid}")

        if event_type == 'initiated':
            logger.debug(f"Call initiated with SID: {call_sid}")
        elif event_type == 'ringing':
            logger.debug(f"Call ringing with SID: {call_sid}")
        elif event_type == 'answered':
            logger.debug(f"Call answered with SID: {call_sid}")
        elif event_type == 'completed':
            logger.debug(f"Call completed with SID: {call_sid}")
        else:
            logger.debug(f"Unhandled call event type: {event_type}")
    except Exception as e:
        logger.error(f"Error handling call event: {e}")
    logger.debug(f"Call event: {request}")
    return '', 200

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
