import base64
import json
import asyncio
from typing import Optional, Any

from fastapi import FastAPI, WebSocket
from fastapi.websockets import WebSocketDisconnect

from backend.core.constants import ResponseMethod
from backend.core.call_manager import call_manager
from backend.services.deepgram_handler import (
    close_deepgram_stt_connection,
    convert_mp3_to_mulaw,
    create_deepgram_stt_connection,
    synthesize_speech
)
from backend.services.openai_utils import invoke_gpt
from backend.services.twilio_utils import create_call
from backend.utils.utils import logger, twilio_client
from backend.core.constants import CallType
from fastapi.websockets import WebSocketState
from fastapi import APIRouter

media_router = APIRouter()

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
            url=f"https://{call_url}/calls/handle_user_call",
            status_callback=f"https://{call_url}/conference/call_events"
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


@media_router.websocket("/media-stream/{session_id}")
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