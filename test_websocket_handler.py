import asyncio
import websockets
import json
from constants import WEBSOCKET_ADDRESS

async def test_websocket():
    uri = f"wss://{WEBSOCKET_ADDRESS}"
    async with websockets.connect(uri) as websocket:
        # Create a test message
        test_message = {
            "event": "media",
            "media": {
                "payload": "test_audio_data_base64"  # Replace with actual base64-encoded audio data if needed
            }
        }
        # Send the test message
        await websocket.send(json.dumps(test_message))
        print("Test message sent")

# Run the test using asyncio.run()
if __name__ == "__main__":
    asyncio.run(test_websocket())

