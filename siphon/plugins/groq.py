from typing import Optional
import os

from livekit.plugins import groq
from . import ClientWrapperMixin

class LLM(ClientWrapperMixin):
    """Groq-backed LLM wrapper around the LiveKit Groq plugin."""
    def __init__(
        self,
        model: Optional[str] = "qwen/qwen3-32b",
        api_key: Optional[str] = None,
        temperature: Optional[int] = 0.3,
        parallel_tool_calls: Optional[bool] = True,
    ) -> None:
        if api_key is None:
            api_key = os.getenv("GROQ_API_KEY")

        self.model = model
        self.api_key= api_key
        self.temperature = temperature
        self.parallel_tool_calls = parallel_tool_calls

        if not self.api_key:
            raise ValueError("GROQ_API_KEY environment variable is not set")

        self._client = self._build_client()

    def _build_client(self):
        return groq.LLM(
            model=self.model,
            api_key=self.api_key,
            temperature=self.temperature,
            parallel_tool_calls=self.parallel_tool_calls
        )
    
    # JSON-serializable view (no Python objects)
    def to_config(self) -> dict:
        return {
            "provider": "groq",
            "model": self.model,
            "temperature": self.temperature,
            "parallel_tool_calls": self.parallel_tool_calls
        }

    # Recreate LLM from config dict
    @classmethod
    def from_config(cls, cfg: dict) -> "LLM":
        return cls(
            model=cfg.get("model"),
            temperature=cfg.get("temperature", 0.3),
            parallel_tool_calls=cfg.get("parallel_tool_calls", True)
        )


class STT(ClientWrapperMixin):
    """Groq-backed STT wrapper around the LiveKit Groq plugin."""
    def __init__(
        self,
        model: Optional[str] = "whisper-large-v3-turbo",
        api_key: Optional[str] = None,
        base_url: Optional[str] = "https://api.groq.com/openai/v1",
        language: Optional[str] = "en",
        detect_language: Optional[bool] = False
    ) -> None:
        if api_key is None:
            api_key = os.getenv("GROQ_API_KEY")

        self.model  = model
        self.api_key = api_key
        self.base_url = base_url
        self.language = language
        self.detect_language = detect_language

        if not self.api_key:
            raise ValueError("GROQ_API_KEY environment variable is not set")

        self._client = self._build_client()

    def _build_client(self):
        return groq.STT(
            model=self.model,
            api_key=self.api_key,
            base_url=self.base_url,
            language=self.language,
            detect_language=self.detect_language,
        )

    # JSON-serializable view (no Python objects)
    def to_config(self) -> dict:
        return {
            "provider": "groq",
            "model": self.model,
            "language": self.language,
            "detect_language": self.detect_language
        }

    # Recreate STT from config dict
    @classmethod
    def from_config(cls, cfg: dict) -> "STT":
        return cls(
            model=cfg.get("model", "whisper-large-v3-turbo"),
            language=cfg.get("language", "en"),
            detect_language=cfg.get("detect_language", False)
        )


class TTS(ClientWrapperMixin):
    """Groq-backed TTS wrapper around the LiveKit Groq plugin."""
    def __init__(
        self,
        model: Optional[str] = "playai-tts",
        voice: Optional[str] = "Arista-PlayAI",
        api_key: Optional[str] = None,
    ) -> None:
        if api_key is None:
            api_key = os.getenv("GROQ_API_KEY")

        self.model = model
        self.voice = voice
        self.api_key = api_key

        if not self.api_key:
            raise ValueError("GROQ_API_KEY environment variable is not set")

        self._client = self._build_client()

    def _build_client(self):
        return groq.TTS(
            model=self.model,
            api_key=self.api_key,
            voice=self.voice,
        )

    # JSON-serializable view (no Python objects)
    def to_config(self) -> dict:
        return {
            "provider": "groq",
            "model": self.model,
            "voice": self.voice
        }

    # Recreate TTS from config dict
    @classmethod
    def from_config(cls, cfg: dict) -> "TTS":
        return cls(
            model=cfg.get("model", "playai-tts"),
            voice=cfg.get("voice", "Arista-PlayAI")
        )