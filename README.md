# AI Call Assistant

An AI-powered call assistant that acts as an intermediary between users and customer service representatives, using speech-to-text, natural language processing, and text-to-speech technologies.

## Project Structure

```
project_root/
├── backend/
│   ├── api/
│   │   ├── app.py          # FastAPI application
│   │   └── routes/         # API routes
│   ├── core/
│   │   ├── call_manager.py # Call session management
│   │   ├── constants.py    # System constants and enums
│   │   └── models.py       # Pydantic models
│   ├── services/
│   │   ├── deepgram_handler.py  # Speech-to-text & text-to-speech
│   │   ├── openai_utils.py      # GPT integration
│   │   ├── prompts.py           # System prompts
│   │   └── twilio_utils.py      # Twilio call handling
│   └── utils/
│       └── utils.py        # Shared utilities
├── scripts/
│   └── initiate_call.sh   # Test script for initiating calls
├── env/
│   └── .env               # Environment variables
└── requirements.txt
```

## Prerequisites

- Python 3.9+
- ngrok for local development
- Twilio account and phone number
- OpenAI API key
- Deepgram API key
- jq (for the test script)

## Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd ai-call-assistant
```

2. Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Set up environment variables in `env/.env`:

```bash
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
OPENAI_API_KEY=your_openai_key
DEEPGRAM_API_KEY=your_deepgram_key
PORT=5050
```

## Running the Application

1. Start ngrok in one terminal:

```bash
ngrok http 5050
```

2. Start the FastAPI server in another terminal:

```bash
python run.py
```

3. Configure Twilio:

   - Go to your Twilio console
   - Update your Twilio phone number's webhook URL to your ngrok URL
   - Set the webhook method to POST
   - Point it to the `/incoming-call` endpoint

4. Test a call using the provided script:

```bash
chmod +x scripts/initiate_call.sh
./scripts/initiate_call.sh
```

## Testing the System

1. The script will initiate a call with this sample payload:

```json
{
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
}
```

2. Use the Twilio phone console to simulate being the customer service agent
3. The AI assistant will handle the conversation using:
   - Deepgram for speech-to-text
   - GPT-4 for natural language processing
   - Deepgram for text-to-speech
   - When needed, it will redirect to the actual user

## Key Features

- Real-time speech processing using Deepgram
- Natural conversation handling with GPT-4
- Conference call management
- Automatic call redirection
- Session state management
- Webhook handling for call events
- WebSocket streaming for audio

## API Endpoints

- `POST /initiate-call`: Start a new call session
- `POST /incoming-call`: Handle incoming Twilio calls
- `WS /media-stream/{session_id}`: WebSocket for real-time audio streaming
- `POST /conference_events/{session_id}`: Handle conference status events
- `POST /call_events`: Handle general call status events
- `POST /handle_user_call`: Handle user callbacks
- `POST /caller_join_conference/{session_id}`: Handle conference joining

## System Flow

1. Call Initiation:

   - Script sends call request with user info
   - System creates a session and initiates calls
   - Bot calls both customer service and waits for connection

2. Call Processing:

   - Speech-to-text processes customer service audio
   - GPT generates appropriate responses
   - Text-to-speech converts responses to audio
   - Audio streamed back to call

3. Redirection:
   - When GPT determines it needs to redirect
   - System calls the actual user
   - Conference is created for all parties
   - Bot is removed from the call

## Troubleshooting

- Ensure ngrok is running and accessible
- Check Twilio webhook configurations
- Verify all API keys are set correctly
- Monitor the application logs for errors
- Ensure the phone numbers in the test script are valid

## Development

To modify the system:

1. Core logic is in `backend/core/`
2. API endpoints in `backend/api/`
3. External services in `backend/services/`
4. Shared utilities in `backend/utils/`

## License

[Your chosen license]
