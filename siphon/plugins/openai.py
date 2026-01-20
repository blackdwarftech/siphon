from typing import Optional
import os

from livekit.plugins import openai
from . import ClientWrapperMixin

class LLM(ClientWrapperMixin):
    """OpenAI-backed LLM wrapper around the LiveKit OpenAI plugin."""
    def __init__(
        self,
        model: Optional[str] = "gpt-4.1-mini",
        base_url: Optional[str] = "https://api.openai.com/v1",
        api_key: Optional[str] = None,
        temperature: Optional[float] = 0.3,
        max_completion_tokens: Optional[int] = 150,
        parallel_tool_calls: Optional[bool] = True,
        timeout: Optional[int] = 15,
    ) -> None:
        if api_key is None:
            api_key = os.getenv("OPENAI_API_KEY")

        self.model = model
        self.base_url = base_url
        self.api_key = api_key
        self.temperature = temperature
        self.max_completion_tokens = max_completion_tokens
        self.parallel_tool_calls = parallel_tool_calls
        self.timeout = timeout

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")

        self._client = self._build_client()

    def _build_client(self):
        return openai.LLM(
            model=self.model,
            base_url=self.base_url,
            api_key=self.api_key,
            temperature=self.temperature,
            max_completion_tokens=self.max_completion_tokens,
            parallel_tool_calls=self.parallel_tool_calls,
            timeout=self.timeout,
        )

    # JSON-serializable view (no Python objects)
    def to_config(self) -> dict:
        return {
            "provider": "openai",
            "model": self.model,
            "base_url": self.base_url,
            "temperature": self.temperature,
            "max_completion_tokens": self.max_completion_tokens,
            "parallel_tool_calls": self.parallel_tool_calls,
            "timeout": self.timeout
        }

    # Recreate LLM from config dict
    @classmethod
    def from_config(cls, cfg: dict) -> "LLM":
        return cls(
            model=cfg.get("model"),
            base_url=cfg.get("base_url"),
            temperature=cfg.get("temperature", 0.3),
            max_completion_tokens=cfg.get("max_completion_tokens"),
            parallel_tool_calls=cfg.get("parallel_tool_calls", True),
            timeout=cfg.get("timeout", 15)
        )
  

class STT(ClientWrapperMixin):
    """OpenAI-backed STT wrapper around the LiveKit OpenAI plugin."""
    def __init__(
        self,
        language: Optional[str] = "en",
        detect_language: Optional[bool] = False,
        model: Optional[str] = "gpt-4o-mini-transcribe",
        api_key: Optional[str] = None,
        use_realtime: Optional[bool] = False
    ) -> None:
        if api_key is None:
            api_key = os.getenv("OPENAI_API_KEY")

        self.language = language
        self.detect_language = detect_language
        self.model= model
        self.api_key = api_key
        self.use_realtime = use_realtime

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")

        self._client = self._build_client()

    def _build_client(self):
        return openai.STT(
            language=self.language,
            detect_language=self.detect_language,
            model=self.model,
            api_key=self.api_key,
            use_realtime=self.use_realtime
        )

    # JSON-serializable view (no Python objects)
    def to_config(self) -> dict:
        return {
            "provider": "openai",
            "model": self.model,
            "language": self.language,
            "detect_language": self.detect_language,
            "use_realtime": self.use_realtime
        }

    # Recreate STT from config dict
    @classmethod
    def from_config(cls, cfg: dict) -> "STT":
        return cls(
            model=cfg.get("model", "gpt-4o-mini-transcribe"),
            language=cfg.get("language", "en"),
            detect_language=cfg.get("detect_language", False),
            use_realtime=cfg.get("use_realtime", False),
        )


class TTS(ClientWrapperMixin):
    """OpenAI-backed TTS wrapper around the LiveKit OpenAI plugin."""
    def __init__(
        self,
        model: Optional[str] = "gpt-4o-mini-tts",
        voice: Optional[str] = "ash",
        instructions: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        if api_key is None:
            api_key = os.getenv("OPENAI_API_KEY")

        self.model = model
        self.voice = voice
        self.instructions = instructions
        self.api_key = api_key

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")

        self._client = self._build_client()

    def _build_client(self):
        return openai.TTS(
            model=self.model,
            voice=self.voice,
            instructions=self.instructions,
            api_key=self.api_key
        )

    # JSON-serializable view (no Python objects)
    def to_config(self) -> dict:
        return {
            "provider": "openai",
            "model": self.model,
            "voice": self.voice,
            "instructions": self.instructions
        }

    # Recreate STT from config dict
    @classmethod
    def from_config(cls, cfg: dict) -> "STT":
        return cls(
            model=cfg.get("model", "gpt-4o-mini-tts"),
            voice=cfg.get("voice", "ash"),
            instructions=cfg.get("instructions", None),
        )

class Realtime(ClientWrapperMixin):
    """OpenAI-backed realtime wrapper around the LiveKit OpenAI plugin."""
    def __init__(
        self,
        model: Optional[str] = "gpt-realtime",
        api_key: Optional[str] = None,
        voice: Optional[str] = "alloy",
        temperature: Optional[int] = 0.3
    ) -> None:
        self.model = model
        self.api_key = api_key
        self.voice = voice
        self.temperature = temperature

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")

        self._client = self._build_client()

    def _build_client(self):
        return openai.realtime.RealtimeModel(
            model=self.model,
            api_key=self.api_key,
            voice=self.voice,
            temperature=self.temperature,
        )

    # JSON-serializable view (no Python objects)
    def to_config(self) -> dict:
        return {
            "provider": "openai",
            "model": self.model,
            "voice": self.voice,
            "temperature": self.temperature
        }

    # Recreate Realtime from config dict
    @classmethod
    def from_config(cls, cfg: dict) -> "Realtime":
        return cls(
            model=cfg.get("model", "gpt-realtime"),
            voice=cfg.get("voice", "alloy"),
            temperature=cfg.get("temperature", 0.3)
        )