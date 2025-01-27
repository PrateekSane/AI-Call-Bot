from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from twilio.twiml.voice_response import VoiceResponse

from backend.core.call_manager import call_manager
from backend.services.twilio_utils import create_conference, end_call
from backend.utils.utils import logger, twilio_client


user_call_router = APIRouter()


@user_call_router.post("/handle_user_call")
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
            call_events_url=f"https://{host}/conference/conference_events/{session_data.session_id}",
            start_conference_on_enter=False, # TODO: Check
            end_conference_on_exit=True
        )
    )

    return HTMLResponse(content=str(response), media_type="application/xml")