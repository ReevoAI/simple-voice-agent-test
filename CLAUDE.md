# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Development
```bash
# Install dependencies (using uv)
uv sync

# Download required models (must run before first use)
uv run python src/agent.py download-files

# Run agent in console mode (direct terminal interaction)
uv run python src/agent.py console

# Run agent in development mode (for frontend/telephony integration)
uv run python src/agent.py dev

# Run agent in production mode
uv run python src/agent.py start
```

### Testing & Quality
```bash
# Run tests with pytest
uv run pytest

# Run specific test
uv run pytest tests/test_agent.py::test_offers_assistance

# Run linter
uv run ruff check src/

# Format code
uv run ruff format src/
```

## Architecture

This is a LiveKit voice AI agent built with the LiveKit Agents Python framework. The core components:

### Agent Pipeline
- **LLM**: OpenAI GPT-4o-mini processes user input and generates responses
- **STT**: Deepgram Nova-3 converts speech to text (multilingual support)
- **TTS**: Cartesia synthesizes speech from LLM responses
- **VAD**: Silero Voice Activity Detection determines when users are speaking
- **Turn Detection**: LiveKit multilingual turn detector manages conversation flow
- **Noise Cancellation**: LiveKit Cloud BVC filters background noise

### Key Design Patterns
- **AgentSession**: Manages the voice pipeline lifecycle and connects components
- **Function Tools**: LLM-callable functions decorated with `@function_tool` for extended capabilities
- **Preemptive Generation**: Agent begins generating responses before user finishes speaking for lower latency
- **Metrics Collection**: Built-in performance monitoring via `MetricsCollectedEvent`
- **False Interruption Handling**: Recovers from noise-triggered interruptions

### Environment Configuration
Required API keys in `.env.local`:
- `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` for LiveKit connection
- `OPENAI_API_KEY` for LLM
- `DEEPGRAM_API_KEY` for STT
- `CARTESIA_API_KEY` for TTS

### Testing Framework
Uses LiveKit's testing framework with:
- Mock tools for simulating function behavior
- LLM-based evaluation via `judge()` for semantic correctness
- Event expectation chains for deterministic behavior validation