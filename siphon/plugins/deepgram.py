from typing import Optional
import os

from livekit.plugins import deepgram
from . import ClientWrapperMixin

class STT(ClientWrapperMixin):
    """Deepgram-backed STT wrapper around the LiveKit Deepgram plugin."""
    def __init__(
        self,
        model: Optional[str] = "nova-3",
        api_key: Optional[str] = None,
        language: Optional[str] = "multi",
        interim_results: Optional[bool] = True,
        smart_format: Optional[bool] = True,
        punctuate: Optional[bool] = True,
        numerals: Optional[bool] = True,
        endpointing_ms: Optional[int] = 175,
        filler_words: Optional[bool] = False,
        profanity_filter: Optional[bool] = False
    ) -> None:
        if api_key is None:
            api_key = os.getenv("DEEPGRAM_API_KEY")

        self.model = model
        self.api_key = api_key
        self.language = language
        self.interim_results = interim_results
        self.smart_format = smart_format
        self.punctuate = punctuate
        self.numerals = numerals
        self.endpointing_ms = endpointing_ms
        self.filler_words = filler_words
        self.profanity_filter = profanity_filter

        if not self.api_key:
            raise ValueError("DEEPGRAM_API_KEY environment variable is not set")

        self._client = self._build_client()

    def _build_client(self):
        return deepgram.STT(
            model=self.model,
            api_key=self.api_key,
            language=self.language,
            interim_results=self.interim_results,
            smart_format=self.smart_format,
            punctuate=self.punctuate,
            numerals=self.numerals,
            endpointing_ms=self.endpointing_ms,
            filler_words=self.filler_words,
            profanity_filter=self.profanity_filter
        )

    # JSON-serializable view (no Python objects)
    def to_config(self) -> dict:
        return {
            "provider": "deepgram",
            "model": self.model,
            "language": self.language,
            "interim_results": self.interim_results,
            "smart_format": self.smart_format,
            "punctuate": self.punctuate,
            "numerals": self.numerals,
            "endpointing_ms": self.endpointing_ms,
            "filler_words": self.filler_words,
            "profanity_filter": self.profanity_filter
        }

    # Recreate STT from config dict
    @classmethod
    def from_config(cls, cfg: dict) -> "STT":
        return cls(
            model=cfg.get("model"),
            language=cfg.get("language", "multi"),
            interim_results=cfg.get("interim_results", True),
            smart_format=cfg.get("smart_format", True),
            punctuate=cfg.get("punctuate", True),
            numerals=cfg.get("numerals", True),
            endpointing_ms=cfg.get("endpointing_ms", 175),
            filler_words=cfg.get("filler_words", False),
            profanity_filter=cfg.get("profanity_filter", False)
        )


class TTS(ClientWrapperMixin):
    """Deepgram-backed TTS wrapper around the LiveKit Deepgram plugin."""
    def __init__(
        self,
        model: Optional[str] = "aura-2-andromeda-en",
        api_key: Optional[str] = None,
        sample_rate: Optional[int] = 24000,
        
    ) -> None:
        if api_key is None:
            api_key = os.getenv("DEEPGRAM_API_KEY")

        self.model = model
        self.api_key = api_key
        self.sample_rate = sample_rate

        if not self.api_key:
            raise ValueError("DEEPGRAM_API_KEY environment variable is not set")

        self._client = self._build_client()

    def _build_client(self):
        return deepgram.TTS(
            model=self.model,
            api_key=self.api_key,
            sample_rate=self.sample_rate
        )

    # JSON-serializable view (no Python objects)
    def to_config(self) -> dict:
        return {
            "provider": "deepgram",
            "model": self.model,
            "sample_rate": self.sample_rate,
        }

    # Recreate TTS from config dict
    @classmethod
    def from_config(cls, cfg: dict) -> "TTS":
        return cls(
            model=cfg.get("model", "aura-2-andromeda-en"),
            sample_rate=cfg.get("sample_rate", 24000),
        )
