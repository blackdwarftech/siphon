from typing import Optional
import os

from livekit.plugins import assemblyai
from . import ClientWrapperMixin

class STT(ClientWrapperMixin):
    """AssemblyAI-backed STT wrapper around the LiveKit AssemblyAI plugin."""
    def __init__(
        self,
        model: Optional[str] = "universal-streaming-multilingual",
        api_key: Optional[str] = None,
        end_of_turn_confidence_threshold: Optional[float] = 0.4,
        min_end_of_turn_silence_when_confident: Optional[int] = 400,
        max_turn_silence: Optional[int] = 1280
    ) -> None:
        if api_key is None:
            api_key = os.getenv("ASSEMBLYAI_API_KEY")

        self.model = model
        self.api_key = api_key
        self.end_of_turn_confidence_threshold = end_of_turn_confidence_threshold
        self.min_end_of_turn_silence_when_confident = min_end_of_turn_silence_when_confident
        self.max_turn_silence = max_turn_silence

        if not self.api_key:
            raise ValueError("ASSEMBLYAI_API_KEY environment variable is not set")

        self._client = self._build_client()

    def _build_client(self):
        return assemblyai.STT(
            model=self.model,
            api_key=self.api_key,
            end_of_turn_confidence_threshold=self.end_of_turn_confidence_threshold,
            min_end_of_turn_silence_when_confident=self.min_end_of_turn_silence_when_confident,
            max_turn_silence=self.max_turn_silence
        )


    # JSON-serializable view (no Python objects)
    def to_config(self) -> dict:
        return {
            "provider": "assemblyai",
            "model": self.model,
            "end_of_turn_confidence_threshold": self.end_of_turn_confidence_threshold,
            "min_end_of_turn_silence_when_confident": self.min_end_of_turn_silence_when_confident,
            "max_turn_silence": self.max_turn_silence
        }

    # Recreate STT from config dict
    @classmethod
    def from_config(cls, cfg: dict) -> "STT":
        return cls(
            model=cfg.get("model"),
            end_of_turn_confidence_threshold=cfg.get("end_of_turn_confidence_threshold", 0.4),
            min_end_of_turn_silence_when_confident=cfg.get("min_end_of_turn_silence_when_confident", 400),
            max_turn_silence=cfg.get("max_turn_silence", 1280)
        )