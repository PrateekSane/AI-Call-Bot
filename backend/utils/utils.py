import os
from twilio.rest import Client
import logging
import ssl
import dotenv
import requests
import time
import json
from loguru import logger

dotenv.load_dotenv('env/.env')


def setup_twilio():
    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')

    return Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


def setup_logging():
    log_file = 'app.log'

    # Remove all existing handlers
    logger.remove()

    # Add file handler
    logger.add(log_file, level="INFO", format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")

    # Add console handler
    logger.add("stdout", level="INFO", format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | {message}", colorize=True)

    # You can configure loguru's output format globally:
    logger.add(
        "stdout", 
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | {message}", 
        level="INFO",
        colorize=True
    )

    if __name__ == "__main__":
        logger.debug("Debug message")
        logger.info("Info message")
        logger.error("Error message")


    return logger

def get_ngrok_url():
    url = "http://127.0.0.1:4040/api/tunnels"
    max_retries = 5
    retries = 0
    url_map = {}
    while retries < max_retries:
        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                for tunnel in data['tunnels']:
                    if tunnel['proto'] == 'https':
                        public_url = tunnel['public_url']
                        url_map[tunnel['config']['addr']] = public_url
                if url_map:
                    return url_map
            time.sleep(1)
            retries += 1
        except requests.exceptions.ConnectionError:
            # ngrok might not be ready yet
            time.sleep(1)
            retries += 1
    raise Exception("ngrok URL not found. Is ngrok running?")


def load_ngrok_addresses():
    try:
        with open('ngrok_addresses.json', 'r') as f:
            ngrok_addresses = json.load(f)
    except FileNotFoundError:
        return None

    return ngrok_addresses

ngrok_addresses = load_ngrok_addresses()
def get_flask_address():
    return ngrok_addresses['FLASK_ADDRESS']

def get_websocket_address():
    return ngrok_addresses['WEBSOCKET_ADDRESS'].replace('https', 'wss')


# Create an SSL context
#ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
#ssl_context.load_cert_chain(certfile="path_to_your_certificate.pem", keyfile="path_to_your_private_key.pem")


twilio_client = setup_twilio()
logger = setup_logging()
