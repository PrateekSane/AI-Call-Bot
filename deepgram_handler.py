import os
from deepgram import DeepgramClient
from deepgram import LiveTranscriptionEvents, LiveOptions
from deepgram import SpeakOptions
from utils import logger
from pydub import AudioSegment
import io

DEEPGRAM_API_KEY = os.getenv('DEEPGRAM_API_KEY')

def get_deepgram_client():
    if not DEEPGRAM_API_KEY:
        logger.error("Missing DEEPGRAM_API_KEY.")
        return None

    return DeepgramClient(api_key=DEEPGRAM_API_KEY)

async def create_deepgram_stt_connection(on_transcript):
    """
    Creates and returns an async Deepgram websocket connection.
    We'll define a callback for receiving transcripts as well.
    """
    deepgram = get_deepgram_client()
    
    dg_connection = deepgram.listen.websocket.v("1")

    # Callback for transcripts
    def on_transcript_event(self, transcript_data, **kwargs):
        sentence = transcript_data.channel.alternatives[0].transcript
        if sentence:
            print(f"Deepgram says: {sentence}")

    # Register the callback
    dg_connection.on(LiveTranscriptionEvents.Transcript, on_transcript_event)

    # Start the connection with LiveOptions
    options = LiveOptions(
        model="nova-2",
        # Add other relevant settings (punctuate, encoding, sample_rate, etc.)
    )
    started_ok = dg_connection.start(options)
    if not started_ok:
        logger.error("Failed to start Deepgram connection.")
        return None
    else:
        logger.info("Deepgram connection started successfully.")
    
    return dg_connection

async def close_deepgram_stt_connection(dg_connection):
    """
    Closes the Deepgram websocket connection asynchronously.
    """
    if dg_connection:
        logger.info("Closing Deepgram connection.")
        dg_connection.finish()

# ------------------ Deepgram TTS ------------------ #
async def synthesize_speech(text: str) -> bytes:
    """
    Use Deepgram TTS to synthesize text. 
    Returns raw audio bytes in the chosen format (e.g., MP3).
    Then we must convert to mu-law if needed for Twilio live streaming.
    """
    deepgram = get_deepgram_client()

    # We can get the audio in memory using .get(...) instead of .save(...).
    # According to docs, this returns a Response object with .content or .raw
    tts_options = SpeakOptions(model="aura-asteria-en")
    body = {"text": text}

    try:
        # This calls the TTS endpoint and returns the audio in memory
        response = deepgram.speak.rest.v("1").get(body, tts_options)
        audio_bytes = response.content  # This is typically MP3 data
        return audio_bytes
    except Exception as e:
        logger.error(f"Error synthesizing speech with Deepgram: {e}")
        return b""


def convert_mp3_to_mulaw(mp3_bytes: bytes) -> bytes:
    """
    Converts MP3 bytes to 8kHz mu-law for Twilio. 
    For demonstration, we rely on ffmpeg or pydub. 
    Here is a simple pydub approach (requires `pip install pydub`).

    If you want to avoid external dependencies, you might run ffmpeg via subprocess.
    """
    try:
        mp3_data = AudioSegment.from_file(io.BytesIO(mp3_bytes), format="mp3")
        # Convert to 8kHz, mono, mu-law
        mu_law_data = mp3_data.set_frame_rate(8000).set_channels(1).set_sample_width(1).export(
            format="raw",
            codec="mulaw",
        )
        return mu_law_data.read()
    except Exception as e:
        logger.error(f"Error converting MP3 to mu-law: {e}")
        return b""
