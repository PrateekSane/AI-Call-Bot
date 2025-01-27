from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from twilio.twiml.voice_response import Connect, VoiceResponse

from backend.core.call_manager import call_manager
from backend.core.constants import CallType
from backend.models.models import InitiateCallRequest
from backend.services.twilio_utils import create_call, create_conference, end_call
from backend.utils.utils import logger, twilio_client


bot_call_router = APIRouter()


@bot_call_router.post("/initiate-call")
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
        existing_sessions_tuple = call_manager.check_session_exists([request.cs_number, request.bot_number, request.user_number])
        if existing_sessions_tuple:
            number, existing_sessions = existing_sessions_tuple
            for session in existing_sessions:
                logger.error(f"Session already exists for {number}. Cleaning up")
                call_manager.delete_session(session)

        session_id = call_manager.create_new_session()
        session_data = call_manager.get_session_by_id(session_id)

        # Set phone numbers, user info (assuming request.user_info is already a valid object)
        session_data.set_bot_number(request.bot_number)
        session_data.set_cs_number(request.cs_number)
        session_data.set_user_number(request.user_number)
        session_data.set_user_info(request.user_info)

        # Build TwiML endpoints
        join_conference_url = f"https://{host}/conference/caller_join_conference/{session_id}"
        call_events_url = f"https://{host}/conference/call_events"

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

@bot_call_router.post("/incoming-call")
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
    connect.stream(url=f'wss://{host}/media/media-stream/{session_data.session_id}')
    response.append(connect)

    return HTMLResponse(content=str(response), media_type="application/xml")
