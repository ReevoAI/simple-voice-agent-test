# Running the LiveKit Agent with External Backend Tool

## Overview
The LiveKit agent uses OpenAI's LLM and has been enhanced with an external backend tool that can be called for specialized responses. The external backend is a FastAPI server that streams responses.

## Setup Instructions

### 1. Install Dependencies
First, sync the updated dependencies:
```bash
uv sync
```

### 2. Start the External Backend (Optional)
If you want to use the external backend tool, start the FastAPI server in one terminal:
```bash
uvicorn external_backend:app --reload --port 8000
```

The external backend will be available at `http://localhost:8000` with two endpoints:

**Reevo-style API (default):**
- Local proxy endpoint: `http://localhost:8000/api/v1/chat`
- Proxies requests to actual Reevo API: `https://api-private.reevo.ai/api/v1/chat`
- Requires JWT authentication in Authorization header
- Headers: `x-reevo-user-id`, `x-reevo-org-id`

**Legacy API:**
- Endpoint: `http://localhost:8000/chat`
- No authentication required

**API Documentation:** `http://localhost:8000/docs`

Note: The external backend is optional. The agent will work without it but won't have access to the `query_reevo_backend` tool.

### 3. Download Required Models
If you haven't already, download the required models:
```bash
uv run python src/agent.py download-files
```

### 4. Run the Agent
In another terminal, run the agent:

**Console mode (direct testing):**
```bash
uv run python src/agent.py console
```

**Development mode (for frontend/telephony):**
```bash
uv run python src/agent.py dev
```

## Architecture

### Core Agent
- Uses **OpenAI GPT-4o-mini** as the main LLM
- **Deepgram Nova-3** for speech-to-text
- **Cartesia** for text-to-speech
- **Silero VAD** for voice activity detection
- **LiveKit turn detector** for conversation flow

### External Backend Tool
The agent has a `query_external_backend` tool that can:
- Call an external API for specialized responses
- Stream responses from the backend
- Pass conversation history for context

### Files
1. **external_backend.py**: FastAPI server that provides specialized responses
2. **src/tools.py**: Contains the `query_external_backend` function tool
3. **src/agent.py**: Main agent with integrated external backend tool

## Using the External Backend Tool

The agent will automatically call the external backend when:
- Users ask for domain-specific information
- The query requires specialized processing
- You explicitly ask to "consult the external service"

### Configuration
Configure in `.env.local`:
- `EXTERNAL_BACKEND_URL`: Backend base URL (default: `http://localhost:8000`)
- `USE_REEVO_API`: Use Reevo-style API with auth (default: `true`, set to `false` for legacy)
- `USE_DIRECT_REEVO_API`: Call Reevo API directly without proxy (default: `false`)
- `REEVO_JWT_TOKEN`: JWT token for authentication (required for Reevo API)
- `REEVO_USER_ID`: User ID for x-reevo-user-id header
- `REEVO_ORG_ID`: Organization ID for x-reevo-org-id header

**API Modes:**
1. **Legacy mode** (`USE_REEVO_API=false`): Uses `/chat` endpoint with mock data
2. **Proxy mode** (`USE_REEVO_API=true`, `USE_DIRECT_REEVO_API=false`): Routes through local backend which calls actual Reevo API
3. **Direct mode** (`USE_DIRECT_REEVO_API=true`): Agent calls Reevo API directly without local backend

### Extending the Backend
To customize the external backend:
1. Modify `external_backend.py` to implement your logic
2. The backend receives messages in OpenAI format: `[{"role": "user", "content": "..."}]`
3. Stream or return responses as needed

## Troubleshooting
- If using the external backend, ensure it's running before the agent needs it
- Check that port 8000 is available for the backend
- Verify all dependencies are installed with `uv sync`
- The agent will handle backend connection errors gracefully