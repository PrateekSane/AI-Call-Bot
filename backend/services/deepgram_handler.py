import os
import asyncio
from deepgram import DeepgramClient
from deepgram import LiveTranscriptionEvents, LiveOptions, SpeakOptions
from pydub import AudioSegment
import io

from backend.utils.utils import logger

def get_deepgram_client():
    api_key = os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        logger.error("Missing DEEPGRAM_API_KEY.")
        return None
    return DeepgramClient(api_key=api_key)

async def create_deepgram_stt_connection(on_transcript):
    dg_client = get_deepgram_client()
    if not dg_client:
        # If client is None, return early
        return None

    dg_connection = dg_client.listen.websocket.v("1")
    loop = asyncio.get_event_loop()

    def on_transcript_event(self, result, **kwargs):
        if not result.channel.alternatives:
            return
        transcript = result.channel.alternatives[0].transcript
        if transcript:
            asyncio.run_coroutine_threadsafe(on_transcript(transcript), loop)

    dg_connection.on(LiveTranscriptionEvents.Transcript, on_transcript_event)

    options = LiveOptions(
        model="nova-2",
        encoding="mulaw",
        sample_rate=8000,
    )
    started_ok = dg_connection.start(options)
    if not started_ok:
        logger.error("Failed to start Deepgram STT connection.")
        return None

    logger.info("Deepgram STT connection started.")
    return dg_connection

async def close_deepgram_stt_connection(dg_connection):
    if dg_connection:
        logger.info("Closing Deepgram connection.")
        dg_connection.finish()

async def synthesize_speech(text: str) -> bytes:
    """
    Use Deepgram TTS to synthesize text in memory.
    """
    tts_deepgram = get_deepgram_client()
    if tts_deepgram is None:
        logger.error("No Deepgram TTS client available.")
        return b""

    tts_options = SpeakOptions(model="aura-asteria-en")
    body = {"text": text}

    try:
        # This calls the TTS endpoint and returns the audio in memory (async)
        tts_response = await tts_deepgram.speak.asyncrest.v("1").stream_memory(body, tts_options)
        audio_buffer = tts_response.stream_memory.getbuffer()
        return audio_buffer.tobytes()
    except Exception as e:
        logger.error(f"Error synthesizing speech with Deepgram: {e}")
        return b""

def convert_mp3_to_mulaw(mp3_bytes: bytes) -> bytes:
    try:
        mp3_data = AudioSegment.from_file(io.BytesIO(mp3_bytes), format="mp3")
        mu_law_data = mp3_data.set_frame_rate(8000).set_channels(1).set_sample_width(1).export(
            format="mulaw",
            codec="pcm_mulaw",
        )
        return mu_law_data.read()
    except Exception as e:
        logger.error(f"Error converting MP3 to mu-law: {e}")
        return b""
