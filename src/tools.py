import json
import logging
import os
from typing import Optional

from livekit.agents import RunContext
from livekit.agents.llm import function_tool

logger = logging.getLogger("tools")


def parse_reevo_streaming_response(raw_response: str) -> str:
    """Parse Reevo API streaming response to extract only text content.

    The Reevo API returns lines with prefixes:
    - 0: text content
    - 9: tool call info
    - a: tool result
    - 2: chat created event
    - e/d: finish reasons
    - f: message metadata
    """
    import re

    lines = raw_response.strip().split("\n")
    text_parts = []

    for line in lines:
        # Skip empty lines
        if not line:
            continue

        # Check if line starts with '0:' which indicates text content
        if line.startswith("0:"):
            # Extract the text after '0:'
            text = line[2:]
            # Try to parse as JSON string
            if text.startswith('"') and text.endswith('"'):
                try:
                    # Remove quotes and parse escape sequences
                    text = json.loads(text)
                    text_parts.append(text)
                except json.JSONDecodeError:
                    # If not valid JSON, use as-is (strip quotes)
                    text_parts.append(text.strip('"'))
            else:
                text_parts.append(text)

    # Join all text parts
    full_text = "".join(text_parts)

    # Remove markdown formatting for better TTS
    # Remove headers (##, ###, etc.)
    full_text = re.sub(r"^#{1,6}\s+", "", full_text, flags=re.MULTILINE)

    # Remove bold/italic markers
    full_text = re.sub(r"\*\*([^*]+)\*\*", r"\1", full_text)  # Bold
    full_text = re.sub(r"\*([^*]+)\*", r"\1", full_text)  # Italic
    full_text = re.sub(r"__([^_]+)__", r"\1", full_text)  # Bold
    full_text = re.sub(r"_([^_]+)_", r"\1", full_text)  # Italic

    # Remove code blocks
    full_text = re.sub(r"```[^`]*```", "", full_text)  # Multi-line code blocks
    full_text = re.sub(r"`([^`]+)`", r"\1", full_text)  # Inline code

    # Remove bullet points and numbered lists
    full_text = re.sub(
        r"^\s*[-*+]\s+", "", full_text, flags=re.MULTILINE
    )  # Bullet points
    full_text = re.sub(
        r"^\s*\d+\.\s+", "", full_text, flags=re.MULTILINE
    )  # Numbered lists

    # Remove links but keep the text
    full_text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", full_text)  # [text](url)

    # Clean up excessive whitespace
    full_text = re.sub(r"\n{3,}", "\n\n", full_text)  # Max 2 newlines
    full_text = re.sub(r" {2,}", " ", full_text)  # Multiple spaces to single

    # Remove any remaining markdown-style dividers
    full_text = re.sub(r"^[-=*]{3,}$", "", full_text, flags=re.MULTILINE)

    return full_text.strip()


@function_tool
async def query_reevo_backend(
    context: RunContext,
    query: str,
    conversation_history: Optional[list[dict[str, str]]] = None,
) -> str:
    """Query the Reevo external backend API for specialized responses. Use it ALWAYS to check if there is meaningful information to be provided, like Meetings, CRM data etc.  Reevo is an All-IN-ONE sales platform.

    This tool streams responses from an external service that can provide domain-specific
    information or custom processing beyond the agent's default capabilities.

    Args:
        query: The user's query to send to the external backend
        conversation_history: Optional conversation history for context

    Returns:
        The response from the external backend
    """
    import aiohttp

    backend_url = os.getenv("EXTERNAL_BACKEND_URL", "http://localhost:8000")
    jwt_token = os.getenv("REEVO_JWT_TOKEN", "")
    user_id = os.getenv("REEVO_USER_ID", "3fa85f64-5717-4562-b3fc-2c963f66afa6")
    org_id = os.getenv("REEVO_ORG_ID", "3fa85f64-5717-4562-b3fc-2c963f66afa6")
    use_reevo_api = os.getenv("USE_REEVO_API", "true").lower() == "true"
    use_direct_reevo = os.getenv("USE_DIRECT_REEVO_API", "false").lower() == "true"

    # Prepare messages in the format expected by the external backend
    messages = []
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": query})

    logger.info("🔧 Tool 'query_reevo_backend' called with:")
    logger.info(f"  - Query: {query}")
    logger.info(
        f"  - Conversation history: {len(conversation_history) if conversation_history else 0} messages"
    )
    logger.info(f"  - Using Reevo API: {use_reevo_api}")
    logger.info(f"  - Direct Reevo API: {use_direct_reevo}")

    # Generate a voice response immediately to let user know we're working
    try:
        # Use the context to get access to the session if available
        if hasattr(context, "session") and context.session:
            context.session.generate_reply(
                instructions="Say 'Let me check that for you' - keep it very brief"
            )
            logger.info("Generated 'checking' voice response")
        else:
            logger.info("Context session not available for voice response")
    except Exception as e:
        logger.warning(f"Could not generate voice response: {e}")

    try:
        result = []

        # Prepare headers and URL based on configuration
        headers = {}

        if use_direct_reevo:
            # Call Reevo API directly
            url = "https://api-ng-private-dev.reevo.ai/api/v1/chat"
            headers = {
                "Authorization": f"Bearer {jwt_token}"
                if jwt_token
                else "Bearer mock-jwt-token",
                "x-reevo-user-id": user_id,
                "x-reevo-org-id": org_id,
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            logger.info(f"  - Calling Reevo API directly: {url}")
        elif use_reevo_api:
            # Use local proxy endpoint
            url = f"{backend_url}/api/v1/chat"
            headers = {
                "Authorization": f"Bearer {jwt_token}"
                if jwt_token
                else "Bearer mock-jwt-token",
                "x-reevo-user-id": user_id,
                "x-reevo-org-id": org_id,
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            logger.info(f"  - Using local Reevo API proxy: {url}")
        else:
            # Use legacy endpoint
            url = f"{backend_url}/chat"
            logger.info(f"  - Using legacy endpoint: {url}")

        async with (
            aiohttp.ClientSession() as session,
            session.post(url, json={"messages": messages}, headers=headers) as resp,
        ):
            resp.raise_for_status()
            # Stream the response
            async for chunk in resp.content.iter_any():
                if chunk:
                    result.append(chunk.decode("utf-8"))

        raw_response = "".join(result)

        # Parse response if using Reevo API
        # if use_direct_reevo or use_reevo_api:
        #     response = parse_reevo_streaming_response(raw_response)
        #     logger.info(f"📥 Raw Reevo response length: {len(raw_response)} chars")
        #     logger.info(
        #         f"📝 Parsed text response: {response[:200]}..."
        #         if len(response) > 200
        #         else f"📝 Parsed text response: {response}"
        #     )
        # else:
        #     # Legacy endpoint returns plain text
        #     response = raw_response
        #     logger.info(
        #         f"📥 Legacy response: {response[:200]}..."
        #         if len(response) > 200
        #         else f"📥 Legacy response: {response}"
        #     )
        #

        response = raw_response

        logger.info(
            "🔧 Tool 'query_reevo_backend' returning clean text for TTS",
            extra={"response": response},
        )
        return response

    except aiohttp.ClientError as e:
        logger.error(f"Error calling external backend: {e}")
        return f"I encountered an error connecting to the external service: {e!s}"
    except Exception as e:
        logger.error(f"Unexpected error calling external backend: {e}")
        return "I'm having trouble accessing the external service right now."
