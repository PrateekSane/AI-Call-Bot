#!/bin/bash

SESSION_STATUS=$(curl -s http://127.0.0.1:4040/api/tunnels)

# Extract the forwarding addresses from ngrok's output
ADDRESSES_JSON=$(curl -s http://127.0.0.1:4040/api/tunnels | \
jq '{
  FLASK_ADDRESS: (.tunnels[] | select(.config.addr=="http://localhost:3000") | .public_url),
  WEBSOCKET_ADDRESS: (.tunnels[] | select(.config.addr=="http://localhost:8100") | .public_url)
}')

# Check if addresses were retrieved
if [[ -z "$ADDRESSES_JSON" || "$ADDRESSES_JSON" == "null" ]]; then
    echo "Failed to retrieve ngrok forwarding addresses."
    exit 1
fi

echo "$ADDRESSES_JSON" > ngrok_addresses.json

# Print the forwarding addresses (optional)
FLASK_ADDRESS=$(echo "$ADDRESSES_JSON" | jq -r '.FLASK_ADDRESS')
WEBSOCKET_ADDRESS=$(echo "$ADDRESSES_JSON" | jq -r '.WEBSOCKET_ADDRESS')

# Print the forwarding addresses (optional)
echo "Forwarding address for port 3000: $FLASK_ADDRESS"
echo "Forwarding address for port 8765: $WEBSOCKET_ADDRESS"

# Call the Python script with the forwarding addresses as arguments
python main.py