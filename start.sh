#!/bin/bash

SESSION_STATUS=$(curl -s http://127.0.0.1:4040/api/tunnels)

# Extract the forwarding addresses from ngrok's output
FORWARDING_3000=$(curl -s http://127.0.0.1:4040/api/tunnels | jq -r '.tunnels[] | select(.proto=="https" and .config.addr=="http://localhost:3000") | .public_url')
# Check if forwarding addresses were found
if [[ -z "$FORWARDING_3000" ]]; then
    echo "Failed to retrieve ngrok forwarding addresses."
    exit 1
fi

# Print the forwarding addresses (optional)
echo "Forwarding address for port 3000: $FORWARDING_3000"

# Call the Python script with the forwarding addresses as arguments
python call_handler.py "$FORWARDING_3000"
