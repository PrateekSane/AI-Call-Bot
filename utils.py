import os
from twilio.rest import Client
import logging
import ssl
import dotenv

dotenv.load_dotenv('env/.env')


def setup_twilio():
    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')

    return Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


def setup_logging():
    log_file = 'app.log'
    logger = logging.getLogger(__name__)

    if not logger.hasHandlers():
        logger.setLevel(logging.INFO)

        # Create file handler
        file_handler = logging.FileHandler(log_file, mode='a', delay=False)
        file_handler.setLevel(logging.INFO)

        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Add both handlers to the logger
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger

import requests
import time

def get_ngrok_url():
    url = "http://127.0.0.1:4040/api/tunnels"
    max_retries = 5
    retries = 0
    while retries < max_retries:
        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                for tunnel in data['tunnels']:
                    if tunnel['proto'] == 'https':
                        public_url = tunnel['public_url']
                        return public_url
            time.sleep(1)
            retries += 1
        except requests.exceptions.ConnectionError:
            # ngrok might not be ready yet
            time.sleep(1)
            retries += 1
    raise Exception("ngrok URL not found. Is ngrok running?")


# Create an SSL context
#ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
#ssl_context.load_cert_chain(certfile="path_to_your_certificate.pem", keyfile="path_to_your_private_key.pem")


twilio_client = setup_twilio()
logger = setup_logging()
