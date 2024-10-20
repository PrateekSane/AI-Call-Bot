import argparse
from flask import Flask, g
from utils import logger
from routes import main

app = Flask(__name__)
app.register_blueprint(main)


def main():
    run_locally = True
    if run_locally:
        parser = argparse.ArgumentParser(description='Set ngrok forwarding addresses as environment variables.')
        parser.add_argument('forwarding_address_3000', type=str, help='Forwarding address for port 3000')
        parser.add_argument('forwarding_address_8765', type=str, help='Forwarding address for port 8765')
        
        args = parser.parse_args()

    print(args.forwarding_address_3000)
    print(args.forwarding_address_8765)
    
    logger.info("Forwarding addresses set as environment variables:")
    logger.info(f"FLASK_ADDRESS forward to: {args.forwarding_address_3000}")
    logger.info(f"WEBSOCKET_ADDRESS forward to: {args.forwarding_address_8765}")
    # Start the Flask app
    app.run(debug=True, port=3000)


if __name__ == "__main__":
    main()