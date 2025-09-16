import re
from typing import AsyncIterable

from livekit import rtc
from livekit.agents.tts import TTS, SynthesizeStream


class PronunciationTTS:
    """TTS wrapper that applies custom pronunciations before synthesis."""

    def __init__(self, base_tts: TTS):
        self._base_tts = base_tts
        self._pronunciations = {
            "Reevo": "Reee Vo",
            "API": "A P I",
            "CRM": "C R M",
            "LiveKit": "Live Kit",
            "JWT": "J W T",
            "HTTP": "H T T P",
            "URL": "U R L",
            "SQL": "sequel",
            "AI": "A I",
        }

    def _apply_pronunciations(self, text: str) -> str:
        """Apply pronunciation rules to text."""
        modified_text = text

        for term, pronunciation in self._pronunciations.items():
            # Use word boundaries to avoid partial replacements
            modified_text = re.sub(
                rf'\b{re.escape(term)}\b',
                pronunciation,
                modified_text,
                flags=re.IGNORECASE
            )

        return modified_text

    def synthesize(self, text: str) -> "SynthesizeStream":
        """Synthesize text with custom pronunciations applied."""
        # Apply pronunciations to the text
        modified_text = self._apply_pronunciations(text)

        # Use the base TTS to synthesize
        return self._base_tts.synthesize(modified_text)

    def stream(self) -> "SynthesizeStream":
        """Create a streaming synthesis session."""
        return self._base_tts.stream()

    # Delegate all other attributes to the base TTS
    def __getattr__(self, name):
        return getattr(self._base_tts, name)

    @property
    def capabilities(self):
        return self._base_tts.capabilities

    @property
    def sample_rate(self):
        return self._base_tts.sample_rate

    @property
    def num_channels(self):
        return self._base_tts.num_channels

    async def aclose(self):
        """Close the TTS instance."""
        if hasattr(self._base_tts, 'aclose'):
            await self._base_tts.aclose()