import os
from twilio.rest import Client
import logging


def setup_twilio():
    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')

    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    return twilio_client


def setup_logging():
    log_file = 'app.log'
    logger = logging.getLogger(__name__)

    # Clear any existing handlers
    logger.handlers.clear()

    logger.setLevel(logging.INFO)

    # Create file handler
    file_handler = logging.FileHandler(log_file, mode='w', delay=False)
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

twilio_client = setup_twilio()
logger = setup_logging()
