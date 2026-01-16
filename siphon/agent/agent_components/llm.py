from typing import Dict, Any

async def get_llm_component(llm_config: Dict[str, Any]) -> Any:
    provider = llm_config.get("provider")
    
    if provider == "gemini":
        from siphon.plugins import gemini
        return gemini.LLM.from_config(llm_config)

    elif provider == "groq":
        from siphon.plugins import groq
        return groq.LLM.from_config(llm_config)
        
    elif provider == "openai":
        from siphon.plugins import openai
        return openai.LLM.from_config(llm_config)
        
    elif provider == "openrouter":
        from siphon.plugins import openrouter
        return openrouter.LLM.from_config(llm_config)

    elif provider == "xai":
        from siphon.plugins import xai
        return xai.LLM.from_config(llm_config)
    
    elif provider == "anthropic":
        from siphon.plugins import anthropic
        return anthropic.LLM.from_config(llm_config)
    
    elif provider == "deepseek":
        from siphon.plugins import deepseek
        return deepseek.LLM.from_config(llm_config)
    
    elif provider == "ollama":
        from siphon.plugins import ollama
        return ollama.LLM.from_config(llm_config)
    
    elif provider == "perplexity":
        from siphon.plugins import perplexity
        return perplexity.LLM.from_config(llm_config)
    
    elif provider == "together":
        from siphon.plugins import together
        return together.LLM.from_config(llm_config)

    elif provider == "mistralai":
        from siphon.plugins import mistralai
        return mistralai.LLM.from_config(llm_config)

    elif provider == "cerebras":
        from siphon.plugins import cerebras
        return cerebras.LLM.from_config(llm_config)
    
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")
