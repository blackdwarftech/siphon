from typing import Dict, Any

async def get_tts_component(tts_config: Dict[str, Any]) -> Any:
    provider = tts_config.get("provider")

    if provider == "cartesia":
        from siphon.plugins import cartesia
        return cartesia.TTS.from_config(tts_config)

    elif provider == "elevenlabs":
        from siphon.plugins import elevenlabs
        return elevenlabs.TTS.from_config(tts_config)

    elif provider == "deepgram":
        from siphon.plugins import deepgram
        return deepgram.TTS.from_config(tts_config)

    elif provider == "gemini":
        from siphon.plugins import gemini
        return gemini.TTS.from_config(tts_config)

    elif provider == "sarvam":
        from siphon.plugins import sarvam
        return sarvam.TTS.from_config(tts_config)

    elif provider == "rime":
        from siphon.plugins import rime
        return rime.TTS.from_config(tts_config)

    elif provider == "google":
        from siphon.plugins import google
        return google.TTS.from_config(tts_config)

    elif provider == "openai":
        from siphon.plugins import openai
        return openai.TTS.from_config(tts_config)

    elif provider == "groq":
        from siphon.plugins import groq
        return groq.TTS.from_config(tts_config)

    else:
        raise ValueError(f"Unsupported TTS provider: {provider}")