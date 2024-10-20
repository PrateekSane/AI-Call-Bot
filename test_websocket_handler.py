import asyncio
import websockets
import json

async def test_websocket():
    uri = "ws://localhost:8765"  # Ensure this matches the server's address and port
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

# Run the test
asyncio.get_event_loop().run_until_complete(test_websocket())

