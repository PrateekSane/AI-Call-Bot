from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from twilio.twiml.voice_response import VoiceResponse

from backend.core.call_manager import call_manager
from backend.services.twilio_utils import create_conference
from backend.utils.utils import logger
from backend.core.constants import TwilioCallStatus, CallType


conference_router = APIRouter()

@conference_router.post("/caller_join_conference/{session_id}")
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

    conference_events_url = f"https://{host}/conference/conference_events/{session_id}"
    response.append(create_conference(conference_name, host, conference_events_url))

    return HTMLResponse(content=str(response), media_type="application/xml")

@conference_router.post("/conference_events/{session_id}")
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


@conference_router.post("/call_events")
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