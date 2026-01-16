from typing import Optional
import os

from livekit.plugins import openai
from . import ClientWrapperMixin

class LLM(ClientWrapperMixin):
    """OpenRouter-backed LLM wrapper for LiveKit's OpenAI-compatible plugin."""
    def __init__(
        self,
        model: Optional[str] = "x-ai/grok-4.1-fast",
        base_url: Optional[str] = "https://openrouter.ai/api/v1",
        api_key: Optional[str] = None,
        temperature: Optional[float] = 0.3,
        max_completion_tokens: Optional[int] = 150,
        parallel_tool_calls: Optional[bool] = True,
        timeout: Optional[int] = 15,
    ) -> None:
        if api_key is None:
            api_key = os.getenv("OPENROUTER_API_KEY")

        self.model = model
        self.base_url = base_url
        self.api_key = api_key
        self.temperature = temperature
        self.max_completion_tokens = max_completion_tokens
        self.parallel_tool_calls = parallel_tool_calls
        self.timeout = timeout

        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable is not set")

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
            "provider": "openrouter",
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
