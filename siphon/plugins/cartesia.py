from typing import Optional
import os

from livekit.plugins import cartesia
from . import ClientWrapperMixin

class STT(ClientWrapperMixin):
    """Cartesia-backed STT wrapper around the LiveKit Cartesia plugin."""
    def __init__(
        self,
        model: Optional[str] = "ink-whisper",
        language: Optional[str] = "en",
        sample_rate: Optional[int] = 16000,
        api_key: Optional[str] = None,
        base_url: Optional[str] = "https://api.cartesia.ai"
    ) -> None:
        if api_key is None:
            api_key = os.getenv("CARTESIA_API_KEY")

        self.model = model
        self.base_url = base_url
        self.language = language
        self.sample_rate = sample_rate
        self.api_key = api_key

        if not self.api_key:
            raise ValueError("CARTESIA_API_KEY environment variable is not set")

        self._client = self._build_client()

    def _build_client(self):
        return cartesia.STT(
            model=self.model,
            language=self.language,
            sample_rate=self.sample_rate,
            api_key=self.api_key,
            base_url=self.base_url
        )


    # JSON-serializable view (no Python objects)
    def to_config(self) -> dict:
        return {
            "provider": "cartesia",
            "model": self.model,
            "sample_rate": self.sample_rate,
            "language": self.language
        }

    # Recreate STT from config dict
    @classmethod
    def from_config(cls, cfg: dict) -> "STT":
        return cls(
            model=cfg.get("model", "ink-whisper"),
            language=cfg.get("language", "en"),
            sample_rate=cfg.get("sample_rate", 16000),
        )

class TTS(ClientWrapperMixin):
    """Cartesia-backed TTS wrapper around the LiveKit Cartesia plugin."""
    def __init__(
        self,
        model: Optional[str] = "sonic-3",
        api_key: Optional[str] = None,
        language: Optional[str] = "en",
        voice: Optional[str] = "f786b574-daa5-4673-aa0c-cbe3e8534c02",
        sample_rate: Optional[int] = 16000
    ) -> None:
        if api_key is None:
            api_key = os.getenv("CARTESIA_API_KEY")

        self.model = model
        self.api_key = api_key
        self.language = language
        self.voice = voice
        self.sample_rate = sample_rate

        if not self.api_key:
            raise ValueError("CARTESIA_API_KEY environment variable is not set")

        self._client = self._build_client()

    def _build_client(self):
        return cartesia.TTS(
            model=self.model,
            api_key=self.api_key,
            language=self.language,
            voice=self.voice,
            sample_rate=self.sample_rate
        )

    # JSON-serializable view (no Python objects)
    def to_config(self) -> dict:
        return {
            "provider": "cartesia",
            "model": self.model,
            "language": self.language,
            "voice": self.voice,
            "sample_rate": self.sample_rate
        }

    # Recreate TTS from config dict
    @classmethod
    def from_config(cls, cfg: dict) -> "TTS":
        return cls(
            model=cfg.get("model", "sonic-3"),
            language=cfg.get("language", "en"),
            voice=cfg.get("voice", "f786b574-daa5-4673-aa0c-cbe3e8534c02"),
            sample_rate=cfg.get("sample_rate", 16000),
        )