import base64
import json
import os
import asyncio
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.websockets import WebSocketDisconnect
from twilio.twiml.voice_response import Connect, VoiceResponse

from backend.core.constants import CallInfo, ResponseMethod, TwilioCallStatus
from backend.core.call_manager import call_manager
from backend.core.models import InitiateCallRequest
from backend.services.deepgram_handler import (
    close_deepgram_stt_connection,
    convert_mp3_to_mulaw,
    create_deepgram_stt_connection,
    synthesize_speech
)
from backend.services.openai_utils import invoke_gpt
from backend.services.twilio_utils import create_call, create_conference, is_redirect, end_call
from backend.utils.utils import logger, twilio_client
from backend.core.constants import CallType

load_dotenv('../env/.env')

PORT = int(os.getenv('PORT', 5050))
app = FastAPI()


@app.get("/", response_class=JSONResponse)
async def index_page():
    return {"message": "Twilio Media Stream Server is running!"}


@app.api_route("/initiate-call", methods=["POST"])
async def initiate_call(request: InitiateCallRequest, req: Request):
    try:
        # End any active calls
        active_calls = twilio_client.calls.list(
            from_=request.cs_number,
            status="in-progress"
        )
        for call in active_calls:
            twilio_client.calls(call.sid).update(status="completed")
            print(f"Ended call with SID: {call.sid}")

        host = req.url.hostname
        session_id = call_manager.create_new_session()
        
        # Store all the call information in the session
        call_manager.set_session_value(session_id, CallInfo.BOT_NUMBER, request.bot_number)
        call_manager.set_session_value(session_id, CallInfo.CS_NUMBER, request.cs_number)
        call_manager.set_session_value(session_id, CallInfo.USER_NUMBER, request.user_number)
        call_manager.set_session_value(session_id, CallInfo.USER_INFO, request.user_info.model_dump())

        join_conference_url = f"https://{host}/caller_join_conference/{session_id}"
        call_events_url = f"https://{host}/call_events"
        
        # Create bot call
        outgoing_conf_bot_call = create_call(
            twilio_client, 
            to=request.bot_number,
            from_=request.bot_number,
            url=join_conference_url,
            status_callback=call_events_url
        )
        call_manager.link_call_to_session(outgoing_conf_bot_call.sid, session_id, CallType.CONFERENCE, is_outbound=True)

        # Create customer service call
        cs_call = create_call(
            twilio_client,
            to=request.cs_number,
            from_=request.bot_number,
            url=join_conference_url,
            status_callback=call_events_url
        )
        call_manager.link_call_to_session(cs_call.sid, session_id, CallType.CUSTOMER_SERVICE)
        
        return {"message": "Calls initiated", "session_id": session_id, "cs_call_sid": cs_call.sid}
        
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
    incoming_call_sid = form_data.get('CallSid')
    incoming_number = form_data.get('From')
    
    # Get session_id from the incoming number
    session_data = call_manager.get_session_by_number(incoming_number)
    if not session_data:
        logger.error(f"No session found for incoming number: {incoming_number}")
        return JSONResponse(
            status_code=404,
            content={"error": "Session not found"}
        )
    
    session_id = session_data.session_id
    
    call_manager.link_call_to_session(incoming_call_sid, session_id, CallType.STREAM, is_outbound=False)

    response = VoiceResponse()
    response.pause(length=1)
    user_info = call_manager.get_session_value(session_id, CallInfo.USER_INFO)
    user_name = user_info.get('user_name') if user_info else "unknown"
    response.say(f"Hi, I'm a helpful agent working for {user_name}")

    connect = Connect()
    connect.stream(url=f'wss://{host}/media-stream/{session_id}')
    response.append(connect)

    return HTMLResponse(content=str(response), media_type="application/xml")


async def send_websocket_message(websocket: WebSocket, stream_sid: str, event_type: str, payload: any):
    """Send a message through the websocket with the specified event type and payload"""
    if not websocket or not stream_sid:
        raise ValueError("No websocket or streamSid provided. Unable to send message.")
    
    message = {
        "event": event_type,
        "streamSid": stream_sid,
    }
    
    if event_type == "media":
        message["media"] = {"payload": payload}
    elif event_type == "mark":
        message["mark"] = {
            "name": "twiml",
            "payload": payload
        }
        
    await websocket.send_json(message)
    logger.info(f"Sent {event_type} message through websocket")


async def handle_voice_response(gpt_reply, stream_sid, websocket):
    """Handle voice response by converting text to speech and sending audio"""
    if not websocket or not stream_sid:
        raise ValueError("No websocket or streamSid provided. Unable to send TTS audio.")
        
    response_content = gpt_reply.get('response_content')
    logger.info(f"Sending TTS audio with response content: {response_content}")
    if not response_content:
        logger.error("No response content provided in voice response")
        return ""
    
    tts_mp3 = await synthesize_speech(response_content)
    tts_mulaw = convert_mp3_to_mulaw(tts_mp3)
    payload_b64 = base64.b64encode(tts_mulaw).decode("ascii")
    return payload_b64


async def handle_phone_tree(gpt_reply):
    """Handle the phone tree response by generating TwiML to dial the extension"""
    try:
        extension = gpt_reply.get('response_content')
        if not extension:
            logger.error("No extension provided in phone tree response")
            return ""
            
        response = VoiceResponse()
        response.play(digits=extension)
        return str(response)
    except Exception as e:
        logger.error(f"Error handling phone tree: {e}")
        return ""


async def handle_stt_transcript(
    transcript: str,
    session_id: str,
    stream_sid: Optional[str],
    websocket: Optional[WebSocket]
):
    gpt_reply = await invoke_gpt(transcript, session_id, call_manager)
    try:
        logger.info("APPLESS")
        logger.info(f"Sending voice response: {gpt_reply['response_method']}")
        logger.info("ORANGES")
        match gpt_reply["response_method"]:
            case ResponseMethod.NOOP.value:
                logger.info("No operation needed, skipping TTS")
            case ResponseMethod.CALL_BACK.value:
                dial_user(websocket.url.hostname, session_id)
            case ResponseMethod.PHONE_TREE.value:
                twiml_response = await handle_phone_tree(gpt_reply)
                await send_websocket_message(websocket, stream_sid, "mark", twiml_response)
            case ResponseMethod.VOICE.value:
                response = await handle_voice_response(gpt_reply, stream_sid, websocket)
                await send_websocket_message(websocket, stream_sid, "media", response)
            case _:
                logger.error(f"Unknown response method: {gpt_reply['response_method']}")
    except Exception as e:
        logger.error(f"Error handling voice response: {e}")


@app.websocket("/media-stream/{session_id}")
async def handle_media_stream(twilio_websocket: WebSocket, session_id: str):
    """Handle media stream after customer service agent connects."""
    logger.info("Twilio WebSocket connection request received.")
    
    # Accept the websocket connection
    await twilio_websocket.accept()
    
    # Wait for the session to be ready (timeout after 30 seconds)
    timeout = 30
    start_time = asyncio.get_event_loop().time()
    
    while not call_manager.is_stream_ready(session_id):
        if asyncio.get_event_loop().time() - start_time > timeout:
            logger.info("Timeout waiting for session to be ready")
            await twilio_websocket.close()
            return
            
        await asyncio.sleep(1)  # Check every second
        
    # pause before proceeding
    await asyncio.sleep(1)
        
    logger.info("Session ready, proceeding with media stream handling")
    session_info = call_manager.get_session_by_id(session_id)
    if not session_info:
        logger.error(f"Session not found for CallSid: {session_id}")
        await twilio_websocket.close()
        return

    # We'll store the streamSid Twilio sends so we can route our TTS back to Twilio
    twilio_stream_sid = None

    async def on_transcript(transcript: str):
        await handle_stt_transcript(
            transcript=transcript,
            session_id=session_id,
            stream_sid=twilio_stream_sid,
            websocket=twilio_websocket
        )

    # Create Deepgram STT connection
    stt_dg_connection = await create_deepgram_stt_connection(on_transcript)
    if stt_dg_connection is None:
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
                stt_dg_connection.send(audio_bytes)

            elif event_type == "stop":
                logger.info("Received Twilio 'stop' event. Ending stream.")
                break

    except WebSocketDisconnect:
        logger.info("Twilio WS disconnected unexpectedly.")
    except Exception as e:
        logger.error(f"Error reading Twilio WS: {e}")
    finally:
        await close_deepgram_stt_connection(stt_dg_connection)
        await twilio_websocket.close()
        logger.info("Closed Twilio WS and Deepgram STT connection.")


def dial_user(call_url, session_id):
    """Dial the user number when redirect is detected"""
    try:
        session_data = call_manager.get_session_by_id(session_id)
        call = create_call(
            twilio_client,
            to=session_data.user_number,
            from_=session_data.bot_number,
            url=f"https://{call_url}/handle_user_call",
            status_callback=f"https://{call_url}/call_events",
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
    session_data = call_manager.get_session_by_id(session_id)

    response = VoiceResponse()
    response.say(f"Connecting you with {session_data.user_info.get('user_name')} now. Thank you!")

    bot_call_sid = call_manager.get_session_value(session_id, CallInfo.OUTBOUND_BOT_SID)
    end_call(twilio_client, bot_call_sid)
    
    # Add the caller to the conference
    response.append(
        create_conference(
            conference_name=session_data.conference_name,
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
        event_type = form_data.get('CallStatus')
        call_sid = form_data.get('CallSid')
        # Get the session associated with this call
        session_data = call_manager.get_session_for_call(call_sid)
        if not session_data:
            logger.error(f"No session found for call {call_sid}")
            return '', 200
        if event_type == TwilioCallStatus.IN_PROGRESS.value:
            logger.debug(f"Call in progress with SID: {call_sid}")
            # Check if this is the customer service call
            if call_sid == session_data.call_sids.customer_service:
                logger.info("Customer service agent connected, setting stream ready")
                call_manager.set_stream_ready(session_data.session_id, True)
                
        elif event_type == TwilioCallStatus.COMPLETED.value:
            logger.debug(f"Call completed with SID: {call_sid}")
            # If customer service disconnects, mark stream as not ready
            if call_sid == session_data.call_sids.customer_service:
                call_manager.set_stream_ready(session_data.session_id, False)
                
    except Exception as e:
        logger.error(f"Error handling call event: {e}")
    return '', 200


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
