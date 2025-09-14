import logging
import os
from typing import Optional

from livekit.agents import RunContext
from livekit.agents.llm import function_tool

logger = logging.getLogger("tools")


@function_tool
async def query_reevo_backend(
    context: RunContext,
    query: str,
    conversation_history: Optional[list[dict[str, str]]] = None,
) -> str:
    """Query the external backend API for specialized responses.

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

        response = "".join(result)
        logger.info(f"📥 External backend response: {response}")
        logger.info(f"🔧 Tool 'query_reevo_backend' returning: {response}")
        return response

    except aiohttp.ClientError as e:
        logger.error(f"Error calling external backend: {e}")
        return f"I encountered an error connecting to the external service: {e!s}"
    except Exception as e:
        logger.error(f"Unexpected error calling external backend: {e}")
        return "I'm having trouble accessing the external service right now."
