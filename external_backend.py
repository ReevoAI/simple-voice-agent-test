# external_backend.py
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from starlette.responses import StreamingResponse
import asyncio
import aiohttp
from typing import Optional


app = FastAPI()


class ChatRequest(BaseModel):
    messages: list[dict]  # [{"role": "user", "content": "..."}]


async def token_stream(messages):
    # Mock response about a meeting on 9/10
    meeting_response = [
        "Based on our records, ",
        "here are the details ",
        "of the meeting on September 10th: ",
        "\n\n",
        "**Meeting Summary:**\n",
        "- Date: September 10, 2024\n",
        "- Time: 2:00 PM - 3:30 PM EST\n",
        "- Attendees: Sarah Chen (Product Manager), ",
        "John Smith (Engineering Lead), ",
        "Maria Garcia (Design Lead), ",
        "and David Kim (QA Lead)\n",
        "\n**Key Discussion Points:**\n",
        "1. Q4 product roadmap review\n",
        "2. New authentication feature specifications\n",
        "3. Mobile app performance improvements\n",
        "4. Customer feedback analysis from beta testing\n",
        "\n**Action Items:**\n",
        "- Sarah to finalize feature requirements by 9/15\n",
        "- John to provide technical feasibility assessment\n",
        "- Maria to create UI mockups for new features\n",
        "- David to prepare test plan for upcoming sprint\n",
        "\n**Next Meeting:** September 17th at 2:00 PM",
    ]

    # Stream tokens with slight delay to simulate real streaming
    for token in meeting_response:
        yield token
        await asyncio.sleep(0.05)  # Reduced delay for better UX


async def reevo_token_stream(messages):
    """Stream response for the Reevo-style API endpoint"""
    # Check if the last message is asking about a meeting
    last_user_msg = next(
        (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
    ).lower()

    # If asking about meetings, return meeting info, otherwise generic response
    if "meeting" in last_user_msg or "9/10" in last_user_msg or "september" in last_user_msg:
        # Return the meeting details
        meeting_response = [
            "Based on our records, ",
            "here are the details ",
            "of the meeting on September 10th: ",
            "\n\n",
            "**Meeting Summary:**\n",
            "- Date: September 10, 2024\n",
            "- Time: 2:00 PM - 3:30 PM EST\n",
            "- Attendees: Sarah Chen (Product Manager), ",
            "John Smith (Engineering Lead), ",
            "Maria Garcia (Design Lead), ",
            "and David Kim (QA Lead)\n",
            "\n**Key Discussion Points:**\n",
            "1. Q4 product roadmap review\n",
            "2. New authentication feature specifications\n",
            "3. Mobile app performance improvements\n",
            "4. Customer feedback analysis from beta testing\n",
            "\n**Action Items:**\n",
            "- Sarah to finalize feature requirements by 9/15\n",
            "- John to provide technical feasibility assessment\n",
            "- Maria to create UI mockups for new features\n",
            "- David to prepare test plan for upcoming sprint\n",
            "\n**Next Meeting:** September 17th at 2:00 PM",
        ]
    else:
        # Generic response for other queries
        meeting_response = [
            "I can help you with information about meetings, ",
            "schedules, and project updates. ",
            "Please ask me about specific meetings or dates, ",
            "and I'll provide you with the relevant details."
        ]

    # Stream tokens with slight delay to simulate real streaming
    for token in meeting_response:
        yield token
        await asyncio.sleep(0.03)


@app.post("/chat")
async def chat(req: ChatRequest):
    """Legacy endpoint for backward compatibility"""
    return StreamingResponse(token_stream(req.messages), media_type="text/plain")


def parse_reevo_streaming_response(chunks):
    """Parse Reevo API streaming response to extract only text content."""
    import json
    import re

    text_parts = []

    for chunk in chunks:
        lines = chunk.strip().split('\n')
        for line in lines:
            # Skip empty lines
            if not line:
                continue

            # Check if line starts with '0:' which indicates text content
            if line.startswith('0:'):
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
    full_text = ''.join(text_parts)

    # Remove markdown formatting for better TTS
    # Remove headers (##, ###, etc.)
    full_text = re.sub(r'^#{1,6}\s+', '', full_text, flags=re.MULTILINE)

    # Remove bold/italic markers
    full_text = re.sub(r'\*\*([^*]+)\*\*', r'\1', full_text)  # Bold
    full_text = re.sub(r'\*([^*]+)\*', r'\1', full_text)  # Italic
    full_text = re.sub(r'__([^_]+)__', r'\1', full_text)  # Bold
    full_text = re.sub(r'_([^_]+)_', r'\1', full_text)  # Italic

    # Remove code blocks
    full_text = re.sub(r'```[^`]*```', '', full_text)  # Multi-line code blocks
    full_text = re.sub(r'`([^`]+)`', r'\1', full_text)  # Inline code

    # Remove bullet points and numbered lists
    full_text = re.sub(r'^\s*[-*+]\s+', '', full_text, flags=re.MULTILINE)  # Bullet points
    full_text = re.sub(r'^\s*\d+\.\s+', '', full_text, flags=re.MULTILINE)  # Numbered lists

    # Remove links but keep the text
    full_text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', full_text)  # [text](url)

    # Clean up excessive whitespace
    full_text = re.sub(r'\n{3,}', '\n\n', full_text)  # Max 2 newlines
    full_text = re.sub(r' {2,}', ' ', full_text)  # Multiple spaces to single

    # Remove any remaining markdown-style dividers
    full_text = re.sub(r'^[-=*]{3,}$', '', full_text, flags=re.MULTILINE)

    return full_text.strip()


async def call_reevo_api(messages, authorization, user_id, org_id, parse_response=True):
    """Make actual call to Reevo API and stream response"""
    reevo_api_url = "https://api-ng-private-dev.reevo.ai/api/v1/chat"

    headers = {
        "Authorization": authorization,
        "x-reevo-user-id": user_id,
        "x-reevo-org-id": org_id,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    # Prepare the request body - Reevo API doesn't use chat_id
    request_body = {
        "messages": messages
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                reevo_api_url,
                json=request_body,
                headers=headers
            ) as resp:
                print(f"Reevo API response status: {resp.status}")

                if resp.status != 200:
                    error_text = await resp.text()
                    print(f"Reevo API error: {error_text}")
                    yield f"Error calling Reevo API: {resp.status} - {error_text}"
                    return

                if parse_response:
                    # Collect all chunks and parse them
                    chunks = []
                    async for chunk in resp.content.iter_any():
                        if chunk:
                            chunks.append(chunk.decode("utf-8"))

                    # Parse the full response to extract text
                    parsed_text = parse_reevo_streaming_response(chunks)
                    print(f"Parsed Reevo response: {parsed_text[:100]}...")

                    # Stream the parsed text back
                    # Split into reasonable chunks for streaming
                    words = parsed_text.split(' ')
                    chunk_size = 5  # Stream 5 words at a time
                    for i in range(0, len(words), chunk_size):
                        chunk = ' '.join(words[i:i+chunk_size])
                        if i + chunk_size < len(words):
                            chunk += ' '
                        yield chunk
                        await asyncio.sleep(0.01)  # Small delay for streaming effect
                else:
                    # Stream raw response
                    async for chunk in resp.content.iter_any():
                        if chunk:
                            yield chunk.decode("utf-8")

    except aiohttp.ClientError as e:
        print(f"Error calling Reevo API: {e}")
        yield f"Error connecting to Reevo API: {str(e)}"
    except Exception as e:
        print(f"Unexpected error: {e}")
        yield f"Unexpected error: {str(e)}"


@app.post("/api/v1/chat")
async def reevo_chat(
    req: ChatRequest,
    authorization: Optional[str] = Header(None),
    x_reevo_user_id: Optional[str] = Header(None),
    x_reevo_org_id: Optional[str] = Header(None),
):
    """Proxy endpoint that forwards requests to actual Reevo API"""

    # Validate authorization header
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    # Log the request headers for debugging
    print(f"Proxying to Reevo API")
    print(f"Auth: {authorization[:30] if authorization else 'None'}...")
    print(f"User ID: {x_reevo_user_id}")
    print(f"Org ID: {x_reevo_org_id}")
    print(f"Messages: {req.messages}")

    # Call actual Reevo API and stream response
    # Parse the response by default to clean it for TTS
    return StreamingResponse(
        call_reevo_api(req.messages, authorization, x_reevo_user_id, x_reevo_org_id, parse_response=True),
        media_type="text/plain"
    )
