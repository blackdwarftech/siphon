from typing import Dict, Any

async def get_stt_component(stt_config: Dict[str, Any]) -> Any:
    provider = stt_config.get("provider")
    
    if provider == "assemblyai":
        from siphon.plugins import assemblyai
        return assemblyai.STT.from_config(stt_config)

    elif provider == "deepgram":
        from siphon.plugins import deepgram
        return deepgram.STT.from_config(stt_config)

    elif provider == "sarvam":
        from siphon.plugins import sarvam
        return sarvam.STT.from_config(stt_config)

    elif provider == "groq":
        from siphon.plugins import groq
        return groq.STT.from_config(stt_config)

    elif provider == "openai":
        from siphon.plugins import openai
        return openai.STT.from_config(stt_config)
    
    elif provider == "cartesia":
        from siphon.plugins import cartesia
        return cartesia.STT.from_config(stt_config)
    
    elif provider == "mistralai":
        from siphon.plugins import mistralai
        return mistralai.STT.from_config(stt_config)

    elif provider == "google":
        from siphon.plugins import google
        return google.STT.from_config(stt_config)

    else:
        raise ValueError(f"Unsupported STT provider: {provider}")