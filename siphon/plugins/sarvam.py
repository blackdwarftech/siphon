from typing import Optional
import os

from livekit.plugins import sarvam
from . import ClientWrapperMixin

class STT(ClientWrapperMixin):
    """Clova-backed STT wrapper around the LiveKit Clova plugin."""
    def __init__(
        self,
        language: Optional[str] = "en-IN",
        model: Optional[str] = "saarika:v2.5",
        api_key: Optional[str] = None,
    ) -> None:
        if api_key is None:
            api_key = os.getenv("SARVAM_API_KEY")

        self.language = language
        self.model = model
        self.api_key = api_key

        if not self.api_key:
            raise ValueError("SARVAM_API_KEY environment variable is not set")

        self._client = self._build_client()

    def _build_client(self):
        return sarvam.STT(
            language=self.language,
            model=self.model,
            api_key=self.api_key,
        )


    # JSON-serializable view (no Python objects)
    def to_config(self) -> dict:
        return {
            "provider": "sarvam",
            "language": self.language,
            "model": self.model,
        }

    # Recreate STT from config dict
    @classmethod
    def from_config(cls, cfg: dict) -> "STT":
        return cls(
            language=cfg.get("language", "en"),
            model=cfg.get("model", "saarika:v2.5"),
        )

class TTS(ClientWrapperMixin):
    """Sarvam-backed TTS wrapper around the Sarvam plugin."""
    def __init__(
        self,
        target_language_code: Optional[str] = "en-IN",
        model: Optional[str] = "bulbul:v2",
        speaker: Optional[str] = "anushka",
        speech_sample_rate: Optional[int] = 22050,
        enable_preprocessing: Optional[bool] = False,
        api_key: Optional[str] = None,
    ) -> None:
        if api_key is None:
            api_key = os.getenv("SARVAM_API_KEY")

        self.target_language_code = target_language_code
        self.model = model
        self.speaker = speaker
        self.speech_sample_rate = speech_sample_rate
        self.enable_preprocessing = enable_preprocessing
        self.api_key = api_key

        if not self.api_key:
            raise ValueError("SARVAM_API_KEY environment variable is not set")

        self._client = self._build_client()

    def _build_client(self):
        return sarvam.TTS(
            target_language_code=self.target_language_code,
            model=self.model,
            speaker=self.speaker,
            speech_sample_rate=self.speech_sample_rate,
            enable_preprocessing=self.enable_preprocessing,
            api_key=self.api_key,
        )

    # JSON-serializable view (no Python objects)
    def to_config(self) -> dict:
        return {
            "provider": "sarvam",
            "target_language_code": self.target_language_code,
            "model": self.model,
            "speaker": self.speaker,
            "speech_sample_rate": self.speech_sample_rate,
            "enable_preprocessing": self.enable_preprocessing,
        }

    # Recreate TTS from config dict
    @classmethod
    def from_config(cls, cfg: dict) -> "TTS":
        return cls(
            target_language_code=cfg.get("target_language_code", "hi-IN"),
            model=cfg.get("model", "bulbul:v2"),
            speaker=cfg.get("speaker", "anushka"),
            speech_sample_rate=cfg.get("speech_sample_rate", 22050),
            enable_preprocessing=cfg.get("enable_preprocessing", False),
        )