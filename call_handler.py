import argparse
from flask import Flask, g
from constants import FLASK_ADDRESS
from utils import logger

app = Flask(__name__)

def main():
    run_locally = True
    if run_locally:
        parser = argparse.ArgumentParser(description='Set ngrok forwarding addresses as environment variables.')
        parser.add_argument('forwarding_address_3000', type=str, help='Forwarding address for port 3000')
        args = parser.parse_args()

    # Save forwarding addresses as global variables
    g.FLASK_ADDRESS = args.forwarding_address_3000
    
    print("Forwarding addresses set as environment variables:")
    print(f"FLASK_ADDRESS: {g.FLASK_ADDRESS}")
    logger.info("Forwarding addresses set as environment variables:")
    logger.info(f"FLASK_ADDRESS: {g.FLASK_ADDRESS}")
    # Start the Flask app
    app.run(debug=True, port=3000)


if __name__ == "__main__":
    main()