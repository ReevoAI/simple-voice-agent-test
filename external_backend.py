# external_backend.py
from fastapi import FastAPI
from pydantic import BaseModel
from starlette.responses import StreamingResponse
import asyncio


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


@app.post("/chat")
async def chat(req: ChatRequest):
    return StreamingResponse(token_stream(req.messages), media_type="text/plain")
