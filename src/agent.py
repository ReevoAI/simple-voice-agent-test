import logging

from dotenv import load_dotenv
from livekit.agents import (
    NOT_GIVEN,
    Agent,
    AgentFalseInterruptionEvent,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    RoomInputOptions,
    RunContext,
    WorkerOptions,
    cli,
    metrics,
)
from livekit.agents.llm import function_tool
from livekit.plugins import cartesia, deepgram, noise_cancellation, openai, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# Import the external backend tool
from tools import query_reevo_backend

logger = logging.getLogger("agent")

load_dotenv(".env.local")


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""You are a helpful voice AI assistant.
            You eagerly assist users with their questions by providing information from your extensive knowledge.
            Your responses are concise, to the point, and without any complex formatting or punctuation including emojis, asterisks, or other symbols.
            You are curious, friendly, and have a sense of humor.

            You have access to an external backend service that can provide specialized responses.
            Use the query_reevo_backend tool when users ask for CRM domain-specific information or
            when you need to consult the external service for specialized processing.""",
        )

    # all functions annotated with @function_tool will be passed to the LLM when this
    # agent is active
    @function_tool
    async def lookup_weather(self, context: RunContext, location: str):
        """Use this tool to look up current weather information in the given location.

        If the location is not supported by the weather service, the tool will indicate this. You must tell the user the location's weather is unavailable.

        Args:
            location: The location to look up weather information for (e.g. city name)
        """

        logger.info(f"🔧 Tool 'lookup_weather' called with location: {location}")

        # Generate a voice response immediately to let user know we're working
        try:
            if hasattr(context, 'session') and context.session:
                context.session.generate_reply(
                    instructions="Say 'Let me check the weather' - keep it very brief"
                )
                logger.info("Generated weather checking voice response")
            else:
                logger.info("Context session not available for weather voice response")
        except Exception as e:
            logger.warning(f"Could not generate weather voice response: {e}")

        return "sunny with a temperature of 70 degrees."

    # Add the external backend query tool as a method
    query_reevo_backend = query_reevo_backend


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    # Logging setup
    # Add any other context you want in all log entries here
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Set up a voice AI pipeline using OpenAI, Cartesia, Deepgram, and the LiveKit turn detector
    session = AgentSession(
        # A Large Language Model (LLM) is your agent's brain, processing user input and generating a response
        # See all providers at https://docs.livekit.io/agents/integrations/llm/
        llm=openai.LLM(model="gpt-4o-mini"),
        # Speech-to-text (STT) is your agent's ears, turning the user's speech into text that the LLM can understand
        # See all providers at https://docs.livekit.io/agents/integrations/stt/
        stt=deepgram.STT(model="nova-3", language="multi"),
        # Text-to-speech (TTS) is your agent's voice, turning the LLM's text into speech that the user can hear
        # See all providers at https://docs.livekit.io/agents/integrations/tts/
        # Switched from Cartesia to OpenAI TTS due to billing issue
        # tts=openai.TTS(voice="nova"),
        tts=cartesia.TTS(voice="6f84f4b8-58a2-430c-8c79-688dad597532"),
        # VAD and turn detection are used to determine when the user is speaking and when the agent should respond
        # See more at https://docs.livekit.io/agents/build/turns
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        # allow the LLM to generate a response while waiting for the end of turn
        # See more at https://docs.livekit.io/agents/build/audio/#preemptive-generation
        preemptive_generation=True,
    )

    # To use a realtime model instead of a voice pipeline, use the following session setup instead:
    # session = AgentSession(
    #     # See all providers at https://docs.livekit.io/agents/integrations/realtime/
    #     llm=openai.realtime.RealtimeModel(voice="marin")
    # )

    # sometimes background noise could interrupt the agent session, these are considered false positive interruptions
    # when it's detected, you may resume the agent's speech
    @session.on("agent_false_interruption")
    def _on_agent_false_interruption(ev: AgentFalseInterruptionEvent):
        logger.info("false positive interruption, resuming")
        session.generate_reply(instructions=ev.extra_instructions or NOT_GIVEN)

    # Debug: Log all available events
    logger.info("Setting up session event handlers...")

    # Try multiple possible event names for function calls
    @session.on("function_calls_started")
    def _on_function_calls_started(ev):
        logger.info(f"🔧 Event 'function_calls_started' triggered with: {ev}")
        for call in ev.function_calls:
            logger.info(
                f"🔧 Tool call started: {call.function_info.name} with arguments: {call.raw_arguments}"
            )

            # Generate a voice response to let user know we're working
            if call.function_info.name == "query_reevo_backend":
                session.generate_reply(
                    instructions="Say 'Let me check that for you' or 'One moment please while I look that up' - keep it very brief and natural"
                )
            elif call.function_info.name == "lookup_weather":
                session.generate_reply(
                    instructions="Say 'Let me check the weather for you' - keep it brief"
                )
            else:
                session.generate_reply(
                    instructions="Say 'One moment please' - keep it very brief"
                )

    # Try alternative event names
    @session.on("function_call_started")
    def _on_function_call_started(ev):
        logger.info(f"🔧 Event 'function_call_started' (singular) triggered with: {ev}")

    @session.on("tool_calls_started")
    def _on_tool_calls_started(ev):
        logger.info(f"🔧 Event 'tool_calls_started' triggered with: {ev}")

    @session.on("tool_call_started")
    def _on_tool_call_started(ev):
        logger.info(f"🔧 Event 'tool_call_started' (singular) triggered with: {ev}")

    # Add a catch-all event handler to see what events are actually fired
    def _debug_all_events(event_name):
        def handler(ev):
            if "function" in event_name.lower() or "tool" in event_name.lower():
                logger.info(f"🔧 DEBUG: Event '{event_name}' triggered with: {ev}")
        return handler

    # Common event patterns to try
    possible_events = [
        "llm_function_call_started",
        "llm_function_calls_started",
        "agent_function_call_started",
        "agent_function_calls_started",
    ]

    for event_name in possible_events:
        try:
            session.on(event_name)(_debug_all_events(event_name))
            logger.info(f"Successfully registered handler for: {event_name}")
        except Exception as e:
            logger.debug(f"Failed to register {event_name}: {e}")

    @session.on("function_calls_finished")
    def _on_function_calls_finished(ev):
        for call in ev.function_calls:
            result = call.result if call.result else "None"
            # Log full result if it's short, otherwise truncate
            if len(str(result)) <= 200:
                logger.info(f"✅ Tool call finished: {call.function_info.name}")
                logger.info(f"   Result: {result}")
            else:
                logger.info(f"✅ Tool call finished: {call.function_info.name}")
                logger.info(f"   Result (truncated): {str(result)[:200]}...")
                logger.info(f"   Full result length: {len(str(result))} characters")

    # Metrics collection, to measure pipeline performance
    # For more information, see https://docs.livekit.io/agents/build/metrics/
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    # # Add a virtual avatar to the session, if desired
    # # For other providers, see https://docs.livekit.io/agents/integrations/avatar/
    # avatar = hedra.AvatarSession(
    #   avatar_id="...",  # See https://docs.livekit.io/agents/integrations/avatar/hedra
    # )
    # # Start the avatar and wait for it to join
    # await avatar.start(session, room=ctx.room)

    # Join the room and connect to the user first
    await ctx.connect()

    # Start the session, which initializes the voice pipeline and warms up the models
    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            # LiveKit Cloud enhanced noise cancellation
            # - If self-hosting, omit this parameter
            # - For telephony applications, use `BVCTelephony` for best results
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    # Generate an initial greeting to start the conversation
    await session.generate_reply(
        instructions="Greet the user warmly and introduce yourself as their Reevo AI assistant. Ask how you can help them today."
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
