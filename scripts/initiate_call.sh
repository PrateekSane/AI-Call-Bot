#!/usr/bin/env bash

# This script retrieves the public ngrok URL and calls the /initiate-call endpoint.

# 1. Get the ngrok tunnel info as JSON
NGROK_API="http://127.0.0.1:4040/api/tunnels"
TUNNELS_JSON="$(curl -s ${NGROK_API})"

# 2. Parse out the public_url
#    (If you have multiple tunnels, you might need to select the correct one)
NGROK_URL="$(echo "$TUNNELS_JSON" | jq -r '.tunnels[0].public_url')"

# If you only have HTTPS tunnels or want to ensure HTTPS, you could do:
# NGROK_URL="$(echo "$TUNNELS_JSON" | jq -r '.tunnels[] | select(.proto=="https") | .public_url')"

# 3. Construct the endpoint you want to call
ENDPOINT="${NGROK_URL}/initiate-call"

# Sample JSON payload
JSON_PAYLOAD='{
    "bot_number": "+12028164470",
    "cs_number": "+14692105627",
    "user_number": "+19164729906",
    "user_info": {
        "user_name": "John Smith",
        "user_email": "john.smith@example.com",
        "reason_for_call": "Double charge on Spotify subscription for $9.99 on March 15th",
        "account_number": "4122563242",
        "additional_info": {
            "subscription_type": "Spotify Premium",
            "charge_date": "2024-03-15",
            "charge_amount": "$9.99",
            "billing_cycle": "Monthly"
        }
    }
}'

echo "Detected ngrok URL: $NGROK_URL"
echo "Calling: $ENDPOINT"
echo "With payload:"
echo "$JSON_PAYLOAD" | jq '.'

# 4. Make the POST request with JSON payload
curl -X POST "$ENDPOINT" \
    -H "Content-Type: application/json" \
    -d "$JSON_PAYLOAD"
echo
