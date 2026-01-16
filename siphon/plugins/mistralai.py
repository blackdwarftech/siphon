from typing import Optional
import os

from livekit.plugins import mistralai
from . import ClientWrapperMixin


class LLM(ClientWrapperMixin):
    """Mistral-backed LLM wrapper for LiveKit's Mistral-compatible plugin."""
    def __init__(
        self,
        model: Optional[str] = "mistral-medium-latest",
        api_key: Optional[str] = None,
        temperature: Optional[float] = 0.3,
        max_completion_tokens: Optional[int] = 150,
        timeout: Optional[int] = 15
    ) -> None:
        if api_key is None:
            api_key = os.getenv("MISTRAL_API_KEY")

        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self.max_completion_tokens = max_completion_tokens
        self.timeout = timeout

        if not self.api_key:
            raise ValueError("MISTRAL_API_KEY environment variable is not set")

        self._client = self._build_client()

    def _build_client(self):
        return mistralai.LLM(
            model=self.model,
            api_key=self.api_key,
            temperature=self.temperature,
            max_completion_tokens=self.max_completion_tokens,
            timeout=self.timeout,
        )

    # JSON-serializable view (no Python objects)
    def to_config(self) -> dict:
        return {
            "provider": "mistralai",
            "model": self.model,
            "temperature": self.temperature,
            "max_completion_tokens": self.max_completion_tokens,
            "timeout": self.timeout
        }

    # Recreate LLM from config dict
    @classmethod
    def from_config(cls, cfg: dict) -> "LLM":
        return cls(
            model=cfg.get("model"),
            temperature=cfg.get("temperature", 0.3),
            max_completion_tokens=cfg.get("max_completion_tokens", 150),
            timeout=cfg.get("timeout", 15),
        )

class STT(ClientWrapperMixin):
    """MistralAI-backed STT wrapper around the LiveKit MistralAI plugin."""
    def __init__(
        self,
        language: Optional[str] = "en",
        model: Optional[str] = "voxtral-mini-latest",
        api_key: Optional[str] = None,
    ) -> None:
        if api_key is None:
            api_key = os.getenv("MISTRAL_API_KEY")

        self.language = language
        self.model = model
        self.api_key = api_key

        if not self.api_key:
            raise ValueError("MISTRAL_API_KEY environment variable is not set")

        self._client = self._build_client()

    def _build_client(self):
        return mistralai.STT(
            language=self.language,
            model=self.model,
            api_key=self.api_key
        )


    # JSON-serializable view (no Python objects)
    def to_config(self) -> dict:
        return {
            "provider": "mistralai",
            "language": self.language,
            "model": self.model
        }

    # Recreate STT from config dict
    @classmethod
    def from_config(cls, cfg: dict) -> "STT":
        return cls(
            language=cfg.get("language", "en"),
            model=cfg.get("model", "voxtral-mini-latest")
        )