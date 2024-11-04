from flask import request, Blueprint, g
from twilio.twiml.voice_response import VoiceResponse, Gather, Dial, Start
from utils import logger, twilio_client
import requests
from datetime import datetime
from constants import TWILIO_NUMBER, TARGET_NUMBER, CONFERENCE_NAME, WEBSOCKET_ADDRESS, CUSTOMER_SERVICE_NUMBER, FLASK_ADDRESS
from call_handler import CallHandler


main = Blueprint('main', __name__)
call_handler = CallHandler(twilio_client)


@main.route("/start_call", methods=['POST'])
def start_call():
    """Initiate calls to the user and customer service, and put them in a conference"""
    bot_call = twilio_client.calls.create(
        to=TWILIO_NUMBER,
        from_=TWILIO_NUMBER,
        url=FLASK_ADDRESS + '/listening_bot_join_conference',
        status_callback=FLASK_ADDRESS + '/dial_events',
        status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
        status_callback_method='POST'
    )

    user_call = twilio_client.calls.create(
        to=TARGET_NUMBER,
        from_=TWILIO_NUMBER,
        url=FLASK_ADDRESS + '/join_conference',
        status_callback=FLASK_ADDRESS + '/dial_events',
        status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
        status_callback_method='POST'
    )

    # Initiate call to customer service
    customer_service_call = twilio_client.calls.create(
        to=CUSTOMER_SERVICE_NUMBER,
        from_=TWILIO_NUMBER,
        url=FLASK_ADDRESS + '/join_conference',
        status_callback=FLASK_ADDRESS + '/dial_events',
        status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
        status_callback_method='POST'
    )

    # Store call SIDs
    call_handler.set_parent_call_sid(user_call.sid, TARGET_NUMBER)
    call_handler.set_child_call_sid(customer_service_call.sid, CUSTOMER_SERVICE_NUMBER)
    call_handler.set_bot_call_sid(bot_call.sid, TWILIO_NUMBER)

    return 'Calls initiated', 200


@main.route("/dial_events", methods=['POST'])
def dial_events():
    params = request.form.to_dict()
    call_sid = params.get('CallSid')
    call_status = params.get('CallStatus')
    logger.info(f"Call {call_status} for CallSid: {call_sid}")
    # Handle events based on call status if necessary
    return '', 200

@main.route("/join_conference", methods=['GET', 'POST'])
def join_conference():
    """Provide TwiML to join the conference"""
    resp = VoiceResponse()
    dial = Dial()
    dial.conference(
        CONFERENCE_NAME,  # TODO: has to be unique otherwise you hear the aids
        start_conference_on_enter=True,
        end_conference_on_exit=False,  # if the CS leaves the conference need to end
        status_callback='/conference_events',
        status_callback_event='start join leave end',
        status_callback_method='POST'
    )
    resp.append(dial)
    return str(resp)

@main.route("/conference_events", methods=['POST'])
def conference_events():
    params = request.form.to_dict()
    event = params.get('StatusCallbackEvent')

    if event == 'conference-start' or event == 'conference-end':
        logger.info(' '.join(event.split('-')) + 'ing')
        return '', 200

    participant_call_sid = params.get('CallSid')
    caller_number = call_handler.get_number_from_sid(participant_call_sid)

    logger.info(f"Conference Event: {event}, CALLER NUMBER: {caller_number}, CallSid: {participant_call_sid}")

    if event == 'participant-join':
        call_handler.handle_conference_join(participant_call_sid)
    elif event == 'participant-leave':
        print("USER LEFT BECAUSE", params.get('ReasonParticipantLeft', 'Unknown'))
        call_handler.handle_conference_leave(participant_call_sid)
    return '', 200

# still need to make it join
@main.route("/listening_bot_join_conference", methods=['GET', 'POST'])
def listening_bot_join_conference():
    response = VoiceResponse()

    # Start streaming
    start = Start()
    start.stream(
        name='BotMediaStream',
        url=f"wss://{WEBSOCKET_ADDRESS}/media"
    )
    response.append(start)

    # Join the conference
    dial = Dial()
    dial.conference(
        CONFERENCE_NAME,  # TODO: has to be unique otherwise you hear the aids
        start_conference_on_enter=True,
        end_conference_on_exit=False,
        status_callback='/conference_events',
        status_callback_event='start join leave end',
        status_callback_method='POST'
    )
    response.append(dial)

    return str(response)