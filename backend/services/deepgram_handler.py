import os
from pydub import AudioSegment
import io
import asyncio

from deepgram import DeepgramClient
from deepgram import LiveTranscriptionEvents, LiveOptions, SpeakOptions

from backend.utils.utils import logger

DEEPGRAM_API_KEY = os.getenv('DEEPGRAM_API_KEY')

def get_deepgram_client():
    if not DEEPGRAM_API_KEY:
        logger.error("Missing DEEPGRAM_API_KEY.")
        return None

    return DeepgramClient(api_key=DEEPGRAM_API_KEY)

async def create_deepgram_stt_connection(on_transcript):
    """
    Create a Deepgram live STT connection. 
    on_transcript is an async callback that receives transcripts from Deepgram.
    """
    dg_client = get_deepgram_client()
    dg_connection = dg_client.listen.websocket.v("1")
    loop = asyncio.get_event_loop()
    # Register the transcript event
    def on_transcript_event(self, result, **kwargs):
        # Grab the transcript string
        if not result.channel.alternatives:
            return
        transcript = result.channel.alternatives[0].transcript
        if transcript:
            # We call the user-provided callback
            asyncio.run_coroutine_threadsafe(on_transcript(transcript), loop)

    dg_connection.on(LiveTranscriptionEvents.Transcript, on_transcript_event)

    # Start the STT connection
    options = LiveOptions(
        model="nova-2",
        encoding="mulaw",  # If Twilio is sending 8kHz mu-law
        sample_rate=8000,
        # punctuate=True, etc.
    )
    started_ok = dg_connection.start(options)
    if not started_ok:
        logger.error("Failed to start Deepgram STT connection.")
        return None

    logger.info("Deepgram STT connection started.")
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
        logger.info(f"Synthesizing speech for: {text}")
        tts_response = await deepgram.speak.asyncrest.v("1").stream_memory(body, tts_options)
        audio_buffer = tts_response.stream_memory.getbuffer()
        audio_bytes = audio_buffer.tobytes()
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
            format="wav",
            codec="pcm_mulaw",
        )
        return mu_law_data.read()
    except Exception as e:
        logger.error(f"Error converting MP3 to mu-law: {e}")
        return b""
