from typing import Optional, Dict, Any
import os

from livekit.plugins import google
from . import ClientWrapperMixin

class STT(ClientWrapperMixin):
    """Google-backed STT wrapper around the LiveKit Google plugin."""
    def __init__(
        self,
        languages: Optional[str] = "en-US",
        detect_language: Optional[bool] = True,
        interim_results: Optional[bool] = True,
        punctuate: Optional[bool] = True,
        model: Optional[str] = "chirp",
        spoken_punctuation: Optional[bool] = False,
        credentials_info: Optional[Dict[str, Any]] = None,
        credentials_file: Optional[str] = None
    ) -> None:
        if credentials_file is None:
            credentials_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", None)

        self.languages = languages
        self.detect_language = detect_language
        self.interim_results = interim_results
        self.punctuate = punctuate
        self.model = model
        self.spoken_punctuation = spoken_punctuation
        self.credentials_info = credentials_info
        self.credentials_file = credentials_file

        if not self.credentials_info or self.credentials_file: 
            raise ValueError("GOOGLE_APPLICATION_CREDENTIALS location is required as environment variable or credentials_info (Array) is required")

        self._client = self._build_client()

    def _build_client(self):
        return google.STT(
            languages=self.languages,
            detect_language=self.detect_language,
            interim_results=self.interim_results,
            punctuate=self.punctuate,
            model=self.model,
            spoken_punctuation=self.spoken_punctuation,
            credentials_info=self.credentials_info,
            credentials_file=self.credentials_file
        )

    # JSON-serializable view (no Python objects)
    def to_config(self) -> dict:
        return {
            "provider": "google",
            "languages": self.languages,
            "detect_language": self.detect_language,
            "interim_results": self.interim_results,
            "punctuate": self.punctuate,
            "model": self.model,
            "spoken_punctuation": self.spoken_punctuation,
            "credentials_info": self.credentials_info
        }

    # Recreate STT from config dict
    @classmethod
    def from_config(cls, cfg: dict) -> "STT":
        return cls(
            languages=cfg.get("languages", "en-US"),
            detect_language=cfg.get("detect_language", True),
            interim_results=cfg.get("interim_results", True),
            punctuate=cfg.get("punctuate", True),
            model=cfg.get("model", "chirp"),
            spoken_punctuation=cfg.get("spoken_punctuation", False),
            credentials_info=cfg.get("credentials_info")
        )


class TTS(ClientWrapperMixin):
    """Google-backed TTS wrapper around the LiveKit Google plugin."""
    def __init__(
        self,
        language: Optional[str] = "en-US",
        gender: Optional[str] = "female",
        voice_name: Optional[str] = "en-US-Standard-H",
        voice_cloning_key: Optional[str] = None,
        sample_rate: Optional[int] = 24000,
        credentials_info: Optional[Dict[str, Any]] = None,
        credentials_file: Optional[str] = None
    ) -> None:
        if credentials_file is None:
            credentials_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", None)

        self.language = language
        self.gender = gender
        self.voice_name = voice_name
        self.voice_cloning_key = voice_cloning_key
        self.sample_rate = sample_rate
        self.credentials_info = credentials_info
        self.credentials_file = credentials_file

        if not self.credentials_info or self.credentials_file: 
            raise ValueError("GOOGLE_APPLICATION_CREDENTIALS location is required as environment variable or credentials_info (Array) is required")

        self._client = self._build_client()

    def _build_client(self):
        return google.TTS(
            language=self.language,
            gender=self.gender,
            voice_name=self.voice_name,
            voice_cloning_key=self.voice_cloning_key,
            sample_rate=self.sample_rate,
            credentials_info=self.credentials_info,
            credentials_file=self.credentials_file
        )

    # JSON-serializable view (no Python objects)
    def to_config(self) -> dict:
        return {
            "provider": "google",
            "language": self.language,
            "gender": self.gender,
            "voice_name": self.voice_name,
            "voice_cloning_key": self.voice_cloning_key,
            "sample_rate": self.sample_rate,
            "credentials_info": self.credentials_info
        }

    # Recreate STT from config dict
    @classmethod
    def from_config(cls, cfg: dict) -> "STT":
        return cls(
            language=cfg.get("language", "en-US"),
            gender=cfg.get("gender", "female"),
            voice_name=cfg.get("voice_name", "en-US-Standard-H"),
            voice_cloning_key=cfg.get("voice_cloning_key"),
            sample_rate=cfg.get("sample_rate", 24000),
            credentials_info=cfg.get("credentials_info")
        )