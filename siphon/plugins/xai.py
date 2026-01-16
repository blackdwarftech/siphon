from typing import Optional
import os

from livekit.plugins import openai
from . import ClientWrapperMixin

class LLM(ClientWrapperMixin):
    """X.AI-backed LLM wrapper for LiveKit's OpenAI-compatible plugin."""
    def __init__(
        self,
        model: Optional[str] = "grok-3-fast",
        base_url: Optional[str] = "https://api.x.ai/v1",
        api_key: Optional[str] = None,
        temperature: Optional[float] = 0.3,
        parallel_tool_calls: Optional[bool] = True
    ) -> None:
        if api_key is None:
            api_key = os.getenv("XAI_API_KEY")

        self.model = model
        self.base_url = base_url
        self.api_key = api_key
        self.temperature = temperature
        self.parallel_tool_calls = parallel_tool_calls

        if not self.api_key:
            raise ValueError("XAI_API_KEY environment variable is not set")

        self._client = self._build_client()

    def _build_client(self):
        return openai.LLM(
            model=self.model,
            base_url=self.base_url,
            api_key=self.api_key,
            temperature=self.temperature,
            parallel_tool_calls=self.parallel_tool_calls,
        )

    # JSON-serializable view (no Python objects)
    def to_config(self) -> dict:
        return {
            "provider": "xai",
            "model": self.model,
            "base_url": self.base_url,
            "temperature": self.temperature,
            "parallel_tool_calls": self.parallel_tool_calls
        }

    # Recreate LLM from config dict
    @classmethod
    def from_config(cls, cfg: dict) -> "LLM":
        return cls(
            model=cfg.get("model"),
            base_url=cfg.get("base_url"),
            temperature=cfg.get("temperature", 0.3),
            parallel_tool_calls=cfg.get("parallel_tool_calls", True),
        )
