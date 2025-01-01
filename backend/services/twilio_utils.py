from twilio.twiml.voice_response import Dial
from twilio.rest import Client


def create_call(twilio_client, to, from_, url, status_callback, 
                status_callback_event=None, status_callback_method='POST'):
    if status_callback_event is None:
        status_callback_event = ['initiated', 'ringing', 'answered', 'completed']
    bot_call = twilio_client.calls.create(
        to=to,
        from_=from_,
        url=url,
        status_callback=status_callback,
        status_callback_event=status_callback_event,
        status_callback_method=status_callback_method
    )
    return bot_call

def create_conference(conference_name, call_events_url, status_callback_event=None, status_callback_method='POST', start_conference_on_enter=True, end_conference_on_exit=False):
    if status_callback_event is None:
        status_callback_event = ['join', 'leave']
    # Add the caller to the conference
    dial = Dial()
    dial.conference(
        conference_name,
        start_conference_on_enter=start_conference_on_enter,
        end_conference_on_exit=end_conference_on_exit,
        status_callback=call_events_url,
        status_callback_event=status_callback_event,
        status_callback_method=status_callback_method,
    )
    return dial


def is_redirect(transcript):
    """Check if the word 'redirect' exists in the transcript"""
    transcript_words = transcript.split()
    transcript_words = [word.lower() for word in transcript_words]
    is_redirect = 'redirect' in transcript_words
    print(f"Is redirect: {is_redirect}")
    return is_redirect

def end_call(twilio_client: Client, call_sid: str):
    twilio_client.calls(call_sid).update(status="completed")