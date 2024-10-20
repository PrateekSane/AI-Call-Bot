import random
import asyncio
import websockets
import base64
import json
from constants import TWILIO_NUMBER, TARGET_NUMBER, FLASK_ADDRESS
from speech_checker import is_hold_message
from utils import twilio_client, logger
from pydub.silence import detect_nonsilent
from pydub import AudioSegment
import io

async def media_stream_handler(websocket, path):
    logger.info("Hold message detected. AHHHHHHHHH")
    async for message in websocket:
        msg = json.loads(message)
        if msg['event'] == 'media':
            audio_data = msg['media']['payload']
            # Decode and process the audio data
            if is_hold_message_audio(audio_data):
                call_user_back()
                break  # Stop processing if needed

def is_hold_message_audio(audio_data):
    return False
    return random.random() < 0.3
    # Decode base64 audio data
    audio_bytes = base64.b64decode(audio_data)
    # Send to speech-to-text API (e.g., Google Cloud Speech-to-Text)
    transcription_text = transcribe_audio(audio_bytes)
    return is_hold_message(transcription_text)

def transcribe_audio(audio_bytes):
    audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format="wav")
    non_silent_ranges = detect_nonsilent(audio, min_silence_len=1000, silence_thresh=-40)
    return len(non_silent_ranges) > 0  # Return True if non-silent segments are found


def call_user_back():
    """Call the user back and merge them into the conference"""
    call = twilio_client.calls.create(
        to=TARGET_NUMBER,
        from_=TWILIO_NUMBER,
        url=FLASK_ADDRESS + '/join_conference',
        method='POST'
    )
    return call


def main():
    logger.info("starting websocket server")
    start_server = websockets.serve(media_stream_handler, '0.0.0.0', 8765)
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()

if __name__ == "__main__":
    main()