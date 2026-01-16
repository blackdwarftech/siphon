from typing import Optional
import os

from livekit.plugins import rime
from . import ClientWrapperMixin

class TTS(ClientWrapperMixin):
    """Rime-backed TTS wrapper around the Rime plugin."""
    def __init__(
        self,
        model: Optional[str] = "arcana",
        speaker: Optional[str] = "celeste",
        lang: Optional[str] = "eng",
        speed_alpha: Optional[float] = 0.9,
        sample_rate: Optional[int] = 16000,
        api_key: Optional[str] = None,
    ) -> None:
        if api_key is None:
            api_key = os.getenv("RIME_API_KEY")

        self.model = model
        self.speaker = speaker
        self.lang = lang
        self.speed_alpha = speed_alpha
        self.sample_rate = sample_rate
        self.api_key = api_key

        if not self.api_key:
            raise ValueError("RIME_API_KEY environment variable is not set")

        self._client = self._build_client()

    def _build_client(self):
        return rime.TTS(
            model=self.model,
            speaker=self.speaker,
            lang=self.lang,
            speed_alpha=self.speed_alpha,
            sample_rate=self.sample_rate,
            api_key=self.api_key,
        )

    # JSON-serializable view (no Python objects)
    def to_config(self) -> dict:
        return {
            "provider": "rime",
            "model": self.model,
            "speaker": self.speaker,
            "lang": self.lang,
            "speed_alpha": self.speed_alpha,
            "sample_rate": self.sample_rate,
        }

    # Recreate TTS from config dict
    @classmethod
    def from_config(cls, cfg: dict) -> "TTS":
        return cls(
            model=cfg.get("model", "arcana"),
            speaker=cfg.get("speaker", "celeste"),
            lang=cfg.get("lang", "eng"),
            speed_alpha=cfg.get("speed_alpha", 0.9),
            sample_rate=cfg.get("sample_rate", 16000)
        )