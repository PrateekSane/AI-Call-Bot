import os
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from pydub import AudioSegment

from backend.services.deepgram_handler import (
    get_deepgram_client,
    create_deepgram_stt_connection,
    close_deepgram_stt_connection,
    synthesize_speech,
    convert_mp3_to_mulaw
)

@pytest.fixture
def mock_logger():
    """
    Patch the logger inside `deepgram_handler`, not `backend.utils.utils.logger`.
    This ensures we intercept the exact reference used by that module.
    """
    with patch("backend.services.deepgram_handler.logger") as m_log:
        yield m_log

@pytest.mark.asyncio
async def test_get_deepgram_client_missing_key(mock_logger):
    with patch.dict(os.environ, {"DEEPGRAM_API_KEY": ""}):
        client = get_deepgram_client()
        assert client is None
        mock_logger.error.assert_called_once_with("Missing DEEPGRAM_API_KEY.")

@pytest.mark.asyncio
async def test_get_deepgram_client_with_key(mock_logger):
    with patch.dict(os.environ, {"DEEPGRAM_API_KEY": "fake_key"}):
        with patch("backend.services.deepgram_handler.DeepgramClient") as mock_client_cls:
            mock_instance = MagicMock()
            mock_client_cls.return_value = mock_instance

            client = get_deepgram_client()
            assert client is not None
            assert client == mock_instance
            mock_logger.error.assert_not_called()

@pytest.mark.asyncio
async def test_create_deepgram_stt_connection_success(mock_logger):
    fake_dg_connection = MagicMock()
    fake_dg_connection.start.return_value = True

    with patch("backend.services.deepgram_handler.get_deepgram_client") as mock_get_client:
        mock_client_instance = MagicMock()
        mock_client_instance.listen.websocket.v.return_value = fake_dg_connection
        mock_get_client.return_value = mock_client_instance

        async def on_transcript_callback(transcript):
            pass

        dg_connection = await create_deepgram_stt_connection(on_transcript_callback)
        assert dg_connection is not None

        # Check calls
        fake_dg_connection.on.assert_called_once()
        fake_dg_connection.start.assert_called_once()
        mock_logger.info.assert_called_with("Deepgram STT connection started.")

@pytest.mark.asyncio
async def test_create_deepgram_stt_connection_start_failure(mock_logger):
    fake_dg_connection = MagicMock()
    fake_dg_connection.start.return_value = False

    with patch("backend.services.deepgram_handler.get_deepgram_client") as mock_get_client:
        mock_client_instance = MagicMock()
        mock_client_instance.listen.websocket.v.return_value = fake_dg_connection
        mock_get_client.return_value = mock_client_instance

        async def on_transcript_callback(transcript):
            pass

        dg_connection = await create_deepgram_stt_connection(on_transcript_callback)
        assert dg_connection is None
        mock_logger.error.assert_called_with("Failed to start Deepgram STT connection.")

@pytest.mark.asyncio
async def test_create_deepgram_stt_connection_no_client(mock_logger):
    with patch("backend.services.deepgram_handler.get_deepgram_client", return_value=None):
        async def on_transcript_callback(transcript):
            pass
        dg_connection = await create_deepgram_stt_connection(on_transcript_callback)
        assert dg_connection is None

@pytest.mark.asyncio
async def test_close_deepgram_stt_connection(mock_logger):
    fake_dg_connection = MagicMock()
    await close_deepgram_stt_connection(fake_dg_connection)
    fake_dg_connection.finish.assert_called_once()
    mock_logger.info.assert_called_with("Closing Deepgram connection.")

@pytest.mark.asyncio
async def test_synthesize_speech_success(mock_logger):
    # Create the final audio buffer mock
    mock_audio_buffer = MagicMock()
    # .tobytes() => b"fake_audio"
    mock_audio_buffer.tobytes.return_value = b"fake_audio"

    # Create a mock "response" object that has `.stream_memory.getbuffer()`
    # returning the buffer mock.
    mock_deepgram_response = MagicMock()
    mock_deepgram_response.stream_memory.getbuffer.return_value = mock_audio_buffer

    # The code does: await tts_deepgram.speak.asyncrest.v("1").stream_memory(body, ...)
    # so let's create an AsyncMock that returns our mock_deepgram_response
    mock_stream_memory = AsyncMock()
    mock_stream_memory.return_value = mock_deepgram_response

    # Make asyncrest.v("1") return an object whose .stream_memory is that async mock
    mock_asyncrest = MagicMock()
    mock_asyncrest.v.return_value.stream_memory = mock_stream_memory

    # Create a mock Deepgram client
    mock_deepgram_client = MagicMock()
    mock_deepgram_client.speak.asyncrest = mock_asyncrest

    # Patch get_deepgram_client so we never use the real environment/API
    with patch("backend.services.deepgram_handler.get_deepgram_client", return_value=mock_deepgram_client):
        # Now run the code
        audio = await synthesize_speech("Hello")
        # Confirm we got bytes from the mocked chain
        assert audio == b"fake_audio"
        # Confirm no error log
        mock_logger.error.assert_not_called()


@pytest.mark.asyncio
async def test_synthesize_speech_error(mock_logger):
    mock_deepgram_client = MagicMock()

    mock_stream_memory_method = AsyncMock(side_effect=Exception("TTS error"))
    mock_asyncrest = MagicMock()
    mock_asyncrest.v.return_value.stream_memory = mock_stream_memory_method
    mock_deepgram_client.speak.asyncrest = mock_asyncrest

    with patch("backend.services.deepgram_handler.get_deepgram_client", return_value=mock_deepgram_client):
        audio = await synthesize_speech("Hello")
        assert audio == b""
        # The code logs "Error synthesizing speech with Deepgram: TTS error"
        mock_logger.error.assert_called_once()
        assert "TTS error" in mock_logger.error.call_args[0][0]

def test_convert_mp3_to_mulaw_success(mock_logger):
    with patch.object(AudioSegment, 'from_file') as mock_from_file:
        mock_audio_segment = MagicMock()
        mock_export = MagicMock()
        mock_export.read.return_value = b"mulaw_data"

        mock_audio_segment.set_frame_rate.return_value = mock_audio_segment
        mock_audio_segment.set_channels.return_value = mock_audio_segment
        mock_audio_segment.set_sample_width.return_value = mock_audio_segment
        mock_audio_segment.export.return_value = mock_export
        mock_from_file.return_value = mock_audio_segment

        result = convert_mp3_to_mulaw(b"fake_mp3_bytes")
        assert result == b"mulaw_data"
        mock_logger.error.assert_not_called()

def test_convert_mp3_to_mulaw_error(mock_logger):
    with patch.object(AudioSegment, 'from_file', side_effect=Exception("Conversion error")):
        result = convert_mp3_to_mulaw(b"fake_mp3_bytes")
        assert result == b""
        mock_logger.error.assert_called_once()
        assert "Conversion error" in mock_logger.error.call_args[0][0]
