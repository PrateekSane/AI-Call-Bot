import random
import asyncio
import websockets
import base64
import json
from constants import TWILIO_NUMBER, TARGET_NUMBER
from speech_checker import is_hold_message
from utils import twilio_client, logger, get_flask_address
from pydub.silence import detect_nonsilent
from pydub import AudioSegment
import whisper
import io
import numpy as np
import torch
import openai

FLASK_ADDRESS = get_flask_address()

model = whisper.load_model("base")

async def media_stream_handler(websocket, path):
    async for message in websocket:
        msg = json.loads(message)
        if msg['event'] == 'media':
            audio_data = msg['media']['payload']
            # Decode and process the audio data
            decoded_audio_data = base64.b64decode(audio_data)
            transcription_text = transcribe_audio(decoded_audio_data)
            print(f"AHHH {transcription_text}")
            if is_hold_message(transcription_text):
                call_user_back()
                break  # Stop processing if needed

def transcribe_audio(audio_bytes):
    # Define the audio parameters (adjust if necessary)
    sample_width = 2      # 16-bit audio (2 bytes per sample)
    frame_rate = 8000     # 8000 Hz sample rate (common for telephony)
    channels = 1          # Mono audio

    try:
        # Load the raw audio data using pydub
        audio = AudioSegment.from_raw(
            io.BytesIO(audio_bytes),
            sample_width=sample_width,
            frame_rate=frame_rate,
            channels=channels
        )

        # Convert audio to mono and set the frame rate to 16000 Hz (required by Whisper)
        audio = audio.set_frame_rate(16000)
        audio = audio.set_channels(1)

        # Convert the audio to a NumPy array and normalize to float32
        samples = np.array(audio.get_array_of_samples()).astype(np.float32)
        samples /= np.iinfo(np.int16).max  # Normalize to range [-1.0, 1.0]

        # Convert the NumPy array to a PyTorch tensor
        samples_tensor = torch.from_numpy(samples)

        # Transcribe the audio using Whisper
        result = model.transcribe(samples_tensor, fp16=False)

        # Get the transcription text
        transcription_text = result["text"]

        return transcription_text.strip()
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        return ""

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
    # start_server = websockets.serve(media_stream_handler, '0.0.0.0', 8200)
    start_server = websockets.serve(
        media_stream_handler, '0.0.0.0', 8100, origins=None
    )
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()

if __name__ == "__main__":
    main()