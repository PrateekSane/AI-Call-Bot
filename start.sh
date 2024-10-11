#!/bin/bash

# Start ngrok for both ports in the background
ngrok http 8765 > ngrok_8765.log &
ngrok http 3000 > ngrok_3000.log &

# Wait for a few seconds to ensure ngrok has started and forwarded addresses are available
sleep 5

# Extract forwarding addresses from ngrok logs
FORWARDING_8765=$(grep -o 'https://[^ ]*' ngrok_8765.log | head -n 1)
FORWARDING_3000=$(grep -o 'https://[^ ]*' ngrok_3000.log | head -n 1)

# Check if forwarding addresses were found
if [[ -z "$FORWARDING_8765" || -z "$FORWARDING_3000" ]]; then
    echo "Failed to retrieve ngrok forwarding addresses."
    exit 1
fi

# Print the forwarding addresses (optional)
echo "Forwarding address for port 8765: $FORWARDING_8765"
echo "Forwarding address for port 3000: $FORWARDING_3000"

# Call the Python script with the forwarding addresses as arguments
python call_handler.py "$FORWARDING_8765" "$FORWARDING_3000"
