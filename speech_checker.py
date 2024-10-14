import asyncio
import websockets
import base64
#from pydub import AudioSegment
#from pydub.silence import detect_nonsilent
import io
import requests
from urllib.parse import urlparse, parse_qs
import os
import openai


openai.api_key = os.getenv("OPENAI_API_KEY")
FLASK_ADDRESS = os.getenv('FLASK_ADDRESS')


def is_human_speech(speech_result: str):
    if not speech_result:
        return False

    system_prompt = "You are an AI assistant that determines if a given text is likely human speech or not."
    user_prompt = f"Is the following text likely to be human speech? Respond with only 'yes' or 'no': '{speech_result}'"
    openai_response = call_llm(system_prompt, user_prompt)

    #is_human = openai_response.choices[0].message['content'].strip().lower() == 'yes'
    is_human = True
    return is_human


def call_llm(system_prompt: str, user_prompt: str):
    """Call OpenAI API to determine if the speech is human"""
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    return response