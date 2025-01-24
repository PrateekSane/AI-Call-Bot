#!/usr/bin/env bash

# This script retrieves the public ngrok URL and calls the /initiate-call endpoint.

# 1. Get the ngrok tunnel info as JSON
NGROK_API="http://127.0.0.1:4040/api/tunnels"
TUNNELS_JSON="$(curl -s ${NGROK_API})"

# 2. Parse out the public_url
NGROK_URL="$(echo "$TUNNELS_JSON" | jq -r '.tunnels[0].public_url')"

# 3. Construct the endpoint you want to call
ENDPOINT="${NGROK_URL}/calls/initiate-call"

# Load the test case from the JSON file
TEST_CASE="$(cat backend/test/test_cases.json | jq '.spotify_double_charge')"

echo "Detected ngrok URL: $NGROK_URL"
echo "Calling: $ENDPOINT"
echo "With payload:"
echo "$TEST_CASE" | jq '.'

# 4. Make the POST request with JSON payload
curl -X POST "$ENDPOINT" \
    -H "Content-Type: application/json" \
    -d "$TEST_CASE"
echo
