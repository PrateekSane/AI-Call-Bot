import asyncio
import websockets
import base64
from pydub import AudioSegment
from pydub.silence import detect_nonsilent
import io
import requests
from urllib.parse import urlparse, parse_qs
import os
import openai

# WebSocket server that handles incoming media streams
async def handle_audio_stream(websocket, path):
    # Extract the call_sid from the WebSocket URL query parameters
    query_params = parse_qs(urlparse(websocket.path).query)
    call_sid = query_params.get('call_sid', [None])[0]

    if call_sid is None:
        print("call_sid not provided")
        return

    async for message in websocket:
        # Twilio sends base64-encoded audio
        decoded_audio = base64.b64decode(message)
        
        # Convert the audio bytes to a WAV file using pydub
        audio = AudioSegment.from_file(io.BytesIO(decoded_audio), format="wav")
        
        print(f"Received {len(decoded_audio)} bytes of audio data")

        # Example: When human speech is detected, send a signal to the Flask app to hang up the call
        if is_human_speech(audio):  # Implement this function for speech detection
            print(f"Human speech detected for call_sid {call_sid}! Sending signal to Flask app to hang up the call.")
            
            # Send a POST request to the Flask app to hang up the call
            requests.post('http://your-flask-server-url/hangup', json={'call_sid': call_sid})

def is_human_speech(audio):
    is_words = detect_speech(audio)
    if is_words:
        # Call OpenAI API to determine if the detected speech is human or not
        openai_response = call_openai_api(audio)
        return openai_response['is_human']

def call_openai_api(audio):
    """Call OpenAI API to determine if the speech is human"""
    # Ensure the OpenAI API key is set
    openai.api_key = os.getenv("OPENAI_API_KEY")

    # Convert audio to text
    audio_file = io.BytesIO(audio.export(format="mp3").read())
    audio_file.name = "speech.mp3"
    
    try:
        transcript = openai.Audio.transcribe("whisper-1", audio_file)
        
        # Use GPT to determine if the transcript is human speech
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an AI assistant that determines if a given text is likely human speech or not."},
                {"role": "user", "content": f"Is the following text likely to be human speech? Respond with only 'yes' or 'no': '{transcript['text']}'"}
            ]
        )
        
        is_human = response.choices[0].message['content'].strip().lower() == 'yes'
        
        return {"is_human": is_human, "transcript": transcript['text']}
    except Exception as e:
        print(f"Error calling OpenAI API: {str(e)}")
        return {"is_human": False, "transcript": ""}

def detect_speech(audio):
    """Detect non-silent segments in the audio"""
    non_silent_ranges = detect_nonsilent(audio, min_silence_len=1000, silence_thresh=-40)
    return len(non_silent_ranges) > 0  # Return True if non-silent segments are found


# Start the WebSocket server
start_server = websockets.serve(handle_audio_stream, "localhost", 8765)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
