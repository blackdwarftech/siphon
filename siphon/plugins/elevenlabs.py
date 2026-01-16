from typing import Optional
import os

from livekit.plugins import elevenlabs
from . import ClientWrapperMixin

class TTS(ClientWrapperMixin):
    """Elevenlabs-backed TTS wrapper around the Elevenlabs Deepgram plugin."""
    def __init__(
        self,
        voice_id: Optional[str] = "bIHbv24MWmeRgasZH58o",
        model: Optional[str] = "eleven_turbo_v2_5",
        api_key: Optional[str] = None,
        inactivity_timeout: Optional[int] = 180,
        auto_mode: Optional[bool] = True,
        language: Optional[str] = "en",
        streaming_latency: Optional[int] = 3,
        enable_ssml_parsing: Optional[bool] = False
    ) -> None:
        if api_key is None:
            api_key = os.getenv("ELEVEN_API_KEY")

        self.voice_id = voice_id
        self.model = model
        self.api_key = api_key
        self.inactivity_timeout = inactivity_timeout
        self.auto_mode = auto_mode
        self.language = language
        self.streaming_latency = streaming_latency
        self.enable_ssml_parsing = enable_ssml_parsing

        if not self.api_key:
            raise ValueError("ELEVEN_API_KEY environment variable is not set")

        self._client = self._build_client()

    def _build_client(self):
        return elevenlabs.TTS(
            voice_id=self.voice_id,
            model=self.model,
            api_key=self.api_key,
            auto_mode=self.auto_mode,
            inactivity_timeout=self.inactivity_timeout,
            language=self.language,
            streaming_latency=self.streaming_latency,
            enable_ssml_parsing=self.enable_ssml_parsing
        )

    # JSON-serializable view (no Python objects)
    def to_config(self) -> dict:
        return {
            "provider": "elevenlabs",
            "voice_id": self.voice_id,
            "model": self.model,
            "inactivity_timeout": self.inactivity_timeout,
            "auto_mode": self.auto_mode,
            "language": self.language,
            "streaming_latency": self.streaming_latency,
            "enable_ssml_parsing": self.enable_ssml_parsing
        }

    # Recreate TTS from config dict
    @classmethod
    def from_config(cls, cfg: dict) -> "TTS":
        return cls(
            voice_id=cfg.get("voice_id", "bIHbv24MWmeRgasZH58o"),
            model=cfg.get("model", "eleven_turbo_v2_5"),
            inactivity_timeout=cfg.get("inactivity_timeout", 180),
            auto_mode=cfg.get("auto_mode", True),
            language=cfg.get("language", "en"),
            streaming_latency=cfg.get("streaming_latency", 3),
            enable_ssml_parsing=cfg.get("enable_ssml_parsing", False),
        )