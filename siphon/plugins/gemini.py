from typing import Optional
import os

from livekit.plugins import google
from . import ClientWrapperMixin

class LLM(ClientWrapperMixin):
    """Gemini-backed LLM wrapper around the LiveKit Google plugin."""
    def __init__(
        self,
        model: Optional[str] = "gemini-2.5-flash-lite",
        api_key: Optional[str] = None,
        max_output_tokens: Optional[int] = 150,
        temperature: Optional[float] = 0.3
    ) -> None:
        self.model = model

        if api_key is None:
            api_key = os.getenv("GEMINI_API_KEY")

        self.api_key = api_key
        self.max_output_tokens = max_output_tokens
        self.temperature = temperature

        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set")

        self._client = self._build_client()

    def _build_client(self):
        return google.LLM(
            model=self.model,
            api_key=self.api_key,
            max_output_tokens=self.max_output_tokens,
            temperature=self.temperature,
        )

    # JSON-serializable view (no Python objects)
    def to_config(self) -> dict:
        return {
            "provider": "gemini",
            "model": self.model,
            "temperature": self.temperature,
            "max_output_tokens": self.max_output_tokens
        }

    # Recreate LLM from config dict
    @classmethod
    def from_config(cls, cfg: dict) -> "LLM":
        return cls(
            model=cfg.get("model"),
            max_output_tokens=cfg.get("max_output_tokens", 150),
            temperature=cfg.get("temperature", 0.3)
        )


class TTS(ClientWrapperMixin):
    """Gemini-backed TTS wrapper around the Google plugin."""
    def __init__(
        self,
        model: Optional[str] = "gemini-2.5-flash-preview-tts",
        voice_name: Optional[str] = "Kore",
        api_key: Optional[str] = None,
    ) -> None:
        self.model = model
        self.voice_name = voice_name

        if api_key is None:
            api_key = os.getenv("GEMINI_API_KEY")

        self.api_key = api_key

        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set")

        self._client = self._build_client()

    def _build_client(self):
        return google.beta.GeminiTTS(
            model=self.model,
            voice_name=self.voice_name,
            api_key=self.api_key,
        )

    # JSON-serializable view (no Python objects)
    def to_config(self) -> dict:
        return {
            "provider": "gemini",
            "voice_name": self.voice_name,
            "model": self.model,
        }

    # Recreate TTS from config dict
    @classmethod
    def from_config(cls, cfg: dict) -> "TTS":
        return cls(
            voice_name=cfg.get("voice_name", "Kore"),
            model=cfg.get("model", "gemini-2.5-flash-preview-tts")
        )

class Realtime(ClientWrapperMixin):
    """Gemini-backed realtime wrapper around the LiveKit Google plugin."""
    def __init__(
        self,
        model: Optional[str] = "gemini-2.5-flash-native-audio-preview-12-2025",
        api_key: Optional[str] = None,
        voice: Optional[str] = "Puck",
        temperature: Optional[int] = 0.3,
        max_output_tokens: Optional[int] = 150
    ) -> None:
        self.model = model
        self.voice = voice
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens

        if api_key is None:
            api_key = os.getenv("GEMINI_API_KEY")

        self.api_key = api_key

        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set")

        self._client = self._build_client()

    def _build_client(self):
        return google.realtime.RealtimeModel(
            model=self.model,
            voice=self.voice,
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
            api_key=self.api_key,
        )

    # JSON-serializable view (no Python objects)
    def to_config(self) -> dict:
        return {
            "provider": "gemini",
            "voice": self.voice,
            "model": self.model,
            "temperature": self.temperature,
            "max_output_tokens": self.max_output_tokens
        }

    # Recreate Realtime from config dict
    @classmethod
    def from_config(cls, cfg: dict) -> "Realtime":
        return cls(
            voice=cfg.get("voice", "Puck"),
            model=cfg.get("model", "gemini-2.5-flash-native-audio-preview-12-2025"),
            temperature=cfg.get("temperature", 0.3),
            max_output_tokens=cfg.get("max_output_tokens", 150)
        )