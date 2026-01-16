from typing import Optional
import os

from livekit.plugins import anthropic
from . import ClientWrapperMixin

class LLM(ClientWrapperMixin):
    """Anthropic-backed LLM wrapper around the LiveKit Anthropic plugin."""
    def __init__(
        self,
        model: Optional[str] = "claude-3-5-sonnet-20241022",
        api_key: Optional[str] = None,
        max_tokens: Optional[int] = 150,
        temperature: Optional[float] = 0.3,
        parallel_tool_calls: Optional[bool] = True
    ) -> None:
        if api_key is None:
            api_key = os.getenv("ANTHROPIC_API_KEY")

        self.model = model
        self.api_key = api_key
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.parallel_tool_calls = parallel_tool_calls

        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set")

        self._client = self._build_client()

    def _build_client(self):
        return anthropic.LLM(
            model=self.model,
            api_key=self.api_key,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            parallel_tool_calls=self.parallel_tool_calls,
        )
    
    # JSON-serializable view (no Python objects)
    def to_config(self) -> dict:
        return {
            "provider": "anthropic",
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "parallel_tool_calls": self.parallel_tool_calls
        }

    # Recreate LLM from config dict
    @classmethod
    def from_config(cls, cfg: dict) -> "LLM":
        return cls(
            model=cfg.get("model"),
            max_tokens=cfg.get("max_tokens", 150),
            temperature=cfg.get("temperature", 0.3),
            parallel_tool_calls=cfg.get("parallel_tool_calls", True)
        )

    