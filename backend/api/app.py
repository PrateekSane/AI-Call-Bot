import base64
import json
import os
import asyncio
from typing import Optional, Any

from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.websockets import WebSocketDisconnect
from twilio.twiml.voice_response import Connect, VoiceResponse

from backend.core.constants import ResponseMethod, TwilioCallStatus
from backend.core.call_manager import call_manager
from backend.core.models import InitiateCallRequest
from backend.services.deepgram_handler import (
    close_deepgram_stt_connection,
    convert_mp3_to_mulaw,
    create_deepgram_stt_connection,
    synthesize_speech
)
from backend.services.openai_utils import invoke_gpt
from backend.services.twilio_utils import create_call, create_conference, end_call
from backend.utils.utils import logger, twilio_client
from backend.core.constants import CallType
from fastapi.websockets import WebSocketState

load_dotenv('../env/.env')

PORT = int(os.getenv('PORT', 5050))
app = FastAPI()


@app.get("/", response_class=JSONResponse)
async def index_page():
    return {"message": "Twilio Media Stream Server is running!"}


@app.api_route("/initiate-call", methods=["POST"])
async def initiate_call(request: InitiateCallRequest, req: Request):
    """
    1. Create a new session via CallManager.
    2. Retrieve SessionData from the manager.
    3. Set phone numbers and user info in SessionData.
    4. Create calls to bot_number and cs_number, link them to the session.
    """
    try:
        # End any active calls from the same CS number
        active_calls = twilio_client.calls.list(from_=request.bot_number, status="in-progress")
        if active_calls:
            for call in active_calls:
                twilio_client.calls(call.sid).update(status="completed")
                logger.info(f"Ended existing in-progress call with SID: {call.sid}")
        host = req.url.hostname
        # Garuntee that no existing session for the given numbers
        existing_sessions = call_manager.check_session_exists([request.cs_number, request.bot_number, request.user_number])
        if existing_sessions:
            number, existing_session = existing_sessions
            logger.error(f"Session already exists for {number}. Cleaning up")
            call_manager.delete_session(existing_session)

        session_id = call_manager.create_new_session()
        session_data = call_manager.get_session_by_id(session_id)

        # Set phone numbers, user info (assuming request.user_info is already a valid object)
        session_data.set_bot_number(request.bot_number)
        session_data.set_cs_number(request.cs_number)
        session_data.set_user_number(request.user_number)
        session_data.set_user_info(request.user_info)

        # Build TwiML endpoints
        join_conference_url = f"https://{host}/caller_join_conference/{session_id}"
        call_events_url = f"https://{host}/call_events"

        # Create a call from the bot number to the "bot number" (not typical, but presumably bridging)
        outgoing_conf_bot_call = create_call(
            twilio_client,
            to=request.bot_number,
            from_=request.bot_number,
            url=join_conference_url,
            status_callback=call_events_url
        )
        # Link this "conference" type call into the manager
        call_manager.link_call_to_session(
            call_sid=outgoing_conf_bot_call.sid,
            call_number=request.bot_number,
            session_id=session_id,
            call_type=CallType.CONFERENCE,
            is_outbound=True
        )

        # Create a call to the customer service number
        cs_call = create_call(
            twilio_client,
            to=request.cs_number,
            from_=request.bot_number,
            url=join_conference_url,
            status_callback=call_events_url
        )
        call_manager.link_call_to_session(
            call_sid=cs_call.sid,
            call_number=request.cs_number,
            session_id=session_id,
            call_type=CallType.CUSTOMER_SERVICE,
        )

        return {"message": "Calls initiated", "session_id": session_id, "outgoing_bot_conference_sid": outgoing_conf_bot_call.sid, "cs_call_sid": cs_call.sid}
    except Exception as e:
        logger.error(f"Error initiating call: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.api_route("/caller_join_conference/{session_id}", methods=["GET", "POST"])
async def caller_join_conference(request: Request, session_id: str):
    """
    Twilio callback for joining a conference. We'll:
    1. Lookup SessionData to get the conference name.
    2. Create a <Dial><Conference> TwiML.
    """
    response = VoiceResponse()
    host = request.url.hostname

    session_data = call_manager.get_session_by_id(session_id)
    if not session_data:
        logger.error(f"No session found with ID: {session_id}")
        return HTMLResponse(content="", media_type="application/xml")

    conference_name = session_data.get_conference_name()

    conference_events_url = f"https://{host}/conference_events/{session_id}"
    response.append(create_conference(conference_name, host, conference_events_url))

    return HTMLResponse(content=str(response), media_type="application/xml")


@app.api_route("/incoming-call", methods=["GET", "POST"])
async def incoming_call(request: Request):
    """
    Twilio webhook for a new inbound call. We'll:
    1. Identify which session is associated with the inbound number.
    2. Link the call SID to that session (STREAM or whatever logic).
    3. Return TwiML that says a greeting and sets up a <Connect><Stream>.
    """
    host = request.url.hostname
    form_data = await request.form()
    incoming_call_sid = form_data.get('CallSid')
    incoming_number = form_data.get('From')

    session_data = call_manager.get_session_by_number(incoming_number)
    if not session_data:
        # TODO: Needs to be able to handle being called directly instead of having to initiate
        # for now kept as returning a 404 if it gets called
        logger.error(f"No session found for incoming number: {incoming_number}")
        return JSONResponse(status_code=404, content={"error": "Session not found"})

    # Link the new call SID into the session as a STREAM call (or however you designate it)
    call_manager.link_call_to_session(
        call_sid=incoming_call_sid,
        call_number=incoming_number,
        session_id=session_data.session_id,
        call_type=CallType.STREAM,
        is_outbound=False
    )

    response = VoiceResponse()
    response.pause(length=1)

    # Retrieve user info from the session
    user_info = session_data.get_user_info()
    # TODO: Needs to be able to handle being called directly instead of having to initiate
    # for now kept as breaking if called directly
    if not user_info:
        logger.error(f"No user info found for session {incoming_call_sid}")
        return HTMLResponse(content="", media_type="application/xml")

    user_name = user_info.user_name
    response.say(f"Hi, I'm a helpful agent working for {user_name}")

    connect = Connect()
    connect.stream(url=f'wss://{host}/media-stream/{session_data.session_id}')
    response.append(connect)

    return HTMLResponse(content=str(response), media_type="application/xml")


async def send_websocket_message(websocket: WebSocket, stream_sid: str, event_type: str, payload: Any):
    """Send a message through the websocket with the specified event type and payload."""
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
    """Convert text to speech -> base64 mu-law -> send over Twilio websocket."""
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
    """Generate TwiML <Play digits="..."> for phone-tree responses."""
    extension = gpt_reply.get('response_content')
    if not extension:
        logger.error("No extension provided in phone tree response")
        return ""

    from twilio.twiml.voice_response import VoiceResponse
    response = VoiceResponse()
    response.play(digits=extension)
    return str(response)


def handle_dial_user(call_url: str, session_id: str):
    """
    Dial the user number when we get a 'redirect' scenario.
    """
    try:
        session_data = call_manager.get_session_by_id(session_id)
        if not session_data:
            logger.error(f"Session not found: {session_id}")
            return None

        user_number = session_data.get_user_number()
        bot_number = session_data.get_bot_number()

        call = create_call(
            twilio_client,
            to=user_number,
            from_=bot_number,
            url=f"https://{call_url}/handle_user_call",
            status_callback=f"https://{call_url}/call_events"
        )
        # For a user call, we can do:
        session_data.set_call_sid(CallType.USER, call.sid)

        logger.info(f"Initiated call to user with SID: {call.sid}")
        return call.sid
    except Exception as e:
        logger.error(f"Error initiating call to user: {e}")
        return None


async def handle_stt_transcript(transcript: str, session_id: str, stream_sid: Optional[str], websocket: Optional[WebSocket]):
    """Pass transcript to GPT, parse the response, and act accordingly."""
    try:
        gpt_reply = await invoke_gpt(transcript, session_id, call_manager)
        match gpt_reply["response_method"]:
            case ResponseMethod.NOOP.value:
                logger.info("No operation needed, skipping TTS. Sleeping for 5 seconds")
                await asyncio.sleep(5)
            case ResponseMethod.CALL_BACK.value:
                # TODO: make the callback work
                # TODO: Have it give a summary of what happened
                if False:
                    handle_dial_user(websocket.url.hostname, session_id)
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
    
async def close_websocket(websocket: WebSocket):
    if websocket.client_state == WebSocketState.CONNECTED:
        await websocket.close()


@app.websocket("/media-stream/{session_id}")
async def handle_media_stream(twilio_websocket: WebSocket, session_id: str):
    """
    1. Wait for session to be 'ready for stream' or time out.
    2. Accept inbound media from Twilio, pass to Deepgram STT.
    3. On transcripts, call handle_stt_transcript and possibly TTS back to Twilio.
    """
    logger.info("Twilio WebSocket connection request received.")
    await twilio_websocket.accept()

    # Wait for the session to be ready for streaming
    timeout = 30
    start_time = asyncio.get_event_loop().time()

    session_data = call_manager.get_session_by_id(session_id)
    if not session_data:
        logger.error(f"Session {session_id} not found")
        await close_websocket(twilio_websocket)
        return

    while not session_data.is_ready_for_stream():
        if asyncio.get_event_loop().time() - start_time > timeout:
            logger.info("Timeout waiting for session to be ready")
            await close_websocket(twilio_websocket)
            return
        await asyncio.sleep(1)

    # Pause briefly
    await asyncio.sleep(1)

    logger.info("Session ready, proceeding with media stream handling")

    twilio_stream_sid = None

    async def on_transcript(transcript: str):
        await handle_stt_transcript(transcript, session_id, twilio_stream_sid, twilio_websocket)

    # Create Deepgram STT connection
    stt_dg_connection = await create_deepgram_stt_connection(on_transcript)
    if stt_dg_connection is None:
        logger.error("Failed to open Deepgram STT. Closing Twilio WS.")
        await close_websocket(twilio_websocket)
        return

    try:
        while True:
            message_text = await twilio_websocket.receive_text()
            data = json.loads(message_text)

            event_type = data.get("event", "")
            if event_type == "start":
                twilio_stream_sid = data["start"]["streamSid"]
                logger.info(f"Twilio stream started: {twilio_stream_sid}")
                # Store in SessionData if needed
                # If you have `session_data.set_twilio_stream_sid(twilio_stream_sid)`:
                if session_data.meta_call_sids:  # or ensure it's not None
                    session_data.set_twilio_stream_sid(twilio_stream_sid)

            elif event_type == "media":
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
        await close_websocket(twilio_websocket)
        logger.info("Closed Twilio WS and Deepgram STT connection.")


@app.api_route("/handle_user_call", methods=['POST'])
async def handle_user_call(request: Request):
    """
    This endpoint is invoked when the newly-dialed user answers.
    We'll greet them and join them to the existing conference.
    """
    host = request.url.hostname
    form_data = await request.form()
    # Twilio sets the "CallSid" of the new inbound call in form_data
    user_call_sid = form_data.get('CallSid')
    # We might not know the session_id directly from user_call_sid. We can look it up:
    session_data = call_manager.get_session_by_call_sid(user_call_sid)
    if not session_data:
        logger.error(f"No session found for user call SID {user_call_sid}")
        return HTMLResponse("", media_type="application/xml")

    response = VoiceResponse()
    user_info = session_data.get_user_info()
    if not user_info:
        logger.error(f"No user info found for session {session_data.session_id}")
        return HTMLResponse("", media_type="application/xml")

    name = user_info.user_name
    # TODO: Use deepgram to say this stuff here
    response.say(f"Connecting you with {name} now. Thank you!")

    # kill all bot calls
    outbots = session_data.call_sids.outbound_bots
    inbots = session_data.call_sids.inbound_bots
    for bot_sid in outbots.extend(inbots):
        end_call(twilio_client, bot_sid)

    # Join the user to the conference
    conference_name = session_data.get_conference_name()
    response.append(
        create_conference(
            conference_name=conference_name,
            call_events_url=f"https://{host}/conference_events/{session_data.session_id}",
            start_conference_on_enter=False,
            end_conference_on_exit=True
        )
    )
    return HTMLResponse(content=str(response), media_type="application/xml")


@app.api_route("/conference_events/{session_id}", methods=['POST'])
async def conference_events(request: Request, session_id: str):
    """
    Twilio calls this webhook on various conference events: participant join/leave, etc.
    We'll store the ConferenceSid in SessionData (if we want).
    """
    try:
        form_data = await request.form()
        event_type = form_data.get('StatusCallbackEvent')
        conference_sid = form_data.get('ConferenceSid')
        call_sid = form_data.get('CallSid')

        session_data = call_manager.get_session_by_id(session_id)
        if not session_data:
            logger.error(f"Conference events: session {session_id} not found")
            return '', 200

        session_data.set_conference_sid(conference_sid)

        logger.info(f"Conference Event: {event_type} for conference {conference_sid} call_sid={call_sid}")

        if event_type == 'participant-join':
            logger.debug(f"Participant joined conference. CallSid: {call_sid}")
            # Possibly check if it's the user or CS and do something
        elif event_type == 'participant-leave':
            reason = form_data.get('ReasonParticipantLeft', 'unknown')
            logger.debug(f"Participant left conference. Reason: {reason}")

        return '', 200
    except Exception as e:
        logger.error(f"Error handling conference event: {e}")
        return str(e), 500


@app.api_route("/call_events", methods=["POST"])
async def call_events(request: Request):
    """
    Handle status changes for any active call. If the CS call is in-progress, we set session ready.
    If the CS call ends, we unset the stream-ready.
    """
    try:
        form_data = await request.form()
        event_type = form_data.get('CallStatus')  # e.g. "in-progress", "completed"
        call_sid = form_data.get('CallSid')

        session_data = call_manager.get_session_by_call_sid(call_sid)
        if not session_data:
            logger.error(f"No session found for call {call_sid}")
            return '', 200

        # Compare the callSid to session_data's known call SIDs
        cs_sid = session_data.call_sids.get_sid(CallType.CUSTOMER_SERVICE)
        if not cs_sid:
            logger.error(f"No customer service call SID found for session {session_data.session_id}")
            return '', 404

        if event_type == TwilioCallStatus.IN_PROGRESS.value:
            logger.debug(f"Call in progress: {call_sid}")
            if call_sid == cs_sid:
                logger.info("Customer service agent connected. Setting stream ready.")
                session_data.set_ready_for_stream()
                
        elif event_type == TwilioCallStatus.COMPLETED.value:
            logger.debug(f"Call completed: {call_sid}")
            if call_sid == cs_sid:
                logger.info("Customer service disconnected. Unsetting stream ready.")
                session_data.unset_ready_for_stream()

    except Exception as e:
        logger.error(f"Error handling call event: {e}")
    return '', 200


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
