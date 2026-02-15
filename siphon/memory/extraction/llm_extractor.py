"""LLM-based fact extraction for LiveKit and other LLM providers."""

import json
from typing import Any, Dict, List, Optional
from datetime import datetime
from siphon.memory.extraction.base import FactExtractor as BaseExtractor
from siphon.memory.extraction.prompts import DEFAULT_EXTRACTION_PROMPT, SYSTEM_PROMPT
from siphon.memory.models import ExtractionResult, Fact
from siphon.config import get_logger

logger = get_logger("calling-agent")


class LLMFactExtractor(BaseExtractor):
    """Extract facts using an LLM (LiveKit, OpenAI, etc.)."""

    def __init__(
        self,
        llm: Any,
        min_importance: int = 6,
        max_facts: int = 15,
    ) -> None:
        super().__init__(min_importance, max_facts)
        self.llm = llm

    async def extract(self, conversation_history: List[Dict[str, Any]]) -> ExtractionResult:
        """Extract facts from conversation using LLM."""
        if not conversation_history:
            logger.warning("No conversation history provided for fact extraction")
            return ExtractionResult(success=True)

        # Format conversation
        conversation_text = self._format_conversation(conversation_history)
        if not conversation_text.strip():
            return ExtractionResult(success=True)

        # Escape curly braces in conversation_text to prevent .format() from interpreting them
        conversation_text = conversation_text.replace("{", "{{").replace("}", "}}")
        prompt = DEFAULT_EXTRACTION_PROMPT.format(conversation_text=conversation_text)

        try:
            result_text = await self._extract_with_llm(prompt)
            
            if not result_text:
                return ExtractionResult(
                    success=False,
                    error_message="LLM returned empty response"
                )

            # Parse JSON response
            facts = self._parse_facts(result_text)
            
            return ExtractionResult(
                facts=facts,
                raw_response=result_text,
                success=len(facts) > 0
            )

        except Exception as e:
            logger.error(f"Error during fact extraction: {e}")
            return ExtractionResult(
                success=False,
                error_message=str(e)
            )

    async def _extract_with_llm(self, prompt: str) -> Optional[str]:
        """Extract using the configured LLM."""
        # Try LiveKit LLM first
        if hasattr(self.llm, 'chat') and callable(getattr(self.llm, 'chat')):
            return await self._extract_with_livekit(prompt)
        
        # Try OpenAI-style
        if hasattr(self.llm, 'chat') and hasattr(self.llm.chat, 'completions'):
            return await self._extract_with_openai(prompt)
        
        logger.warning("No compatible LLM interface found")
        return None

    async def _extract_with_livekit(self, prompt: str) -> Optional[str]:
        """Extract using LiveKit LLM."""
        try:
            from livekit.agents.llm import ChatMessage, ChatContext
            
            chat_ctx = ChatContext([
                ChatMessage(role="system", content=[SYSTEM_PROMPT]),
                ChatMessage(role="user", content=[prompt])
            ])
            
            chunks = []
            chunk_count = 0
            
            async with self.llm.chat(chat_ctx=chat_ctx) as stream:
                async for chunk in stream:
                    chunk_count += 1
                    content = None
                    if hasattr(chunk, 'delta') and chunk.delta:
                        content = getattr(chunk.delta, 'content', None)
                    elif hasattr(chunk, 'content'):
                        content = chunk.content
                    
                    if content:
                        chunks.append(content)
            
            response_text = "".join(chunks)
            logger.info(f"LiveKit LLM collected {chunk_count} chunks, length: {len(response_text)}")
            return response_text if response_text else None
            
        except Exception as e:
            logger.error(f"LiveKit extraction error: {e}")
            return None

    async def _extract_with_openai(self, prompt: str) -> Optional[str]:
        """Extract using OpenAI-style LLM."""
        try:
            response = await self.llm.chat.completions.create(
                model=getattr(self.llm, 'model', 'gpt-4o-mini'),
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1000,
            )
            return response.choices[0].message.content if response.choices else None
        except Exception as e:
            logger.error(f"OpenAI extraction error: {e}")
            return None

    def _parse_facts(self, result_text: str) -> List[Fact]:
        """Parse and validate facts from LLM response."""
        # Clean markdown formatting
        result_text = result_text.strip()
        if result_text.startswith("```json"):
            result_text = result_text[7:]
        if result_text.startswith("```"):
            result_text = result_text[3:]
        if result_text.endswith("```"):
            result_text = result_text[:-3]
        result_text = result_text.strip()

        try:
            data = json.loads(result_text)
        except json.JSONDecodeError:
            # Try to fix partial JSON
            data = self._try_fix_json(result_text)
            if data is None:
                logger.warning("Failed to parse JSON response")
                return []

        if not isinstance(data, list):
            logger.warning(f"Expected list, got {type(data)}: {str(data)[:100]}")
            return []

        facts = []
        now = datetime.utcnow()
        
        for i, item in enumerate(data):
            if not isinstance(item, dict):
                logger.debug(f"Skipping non-dict item at index {i}: {type(item)}")
                continue
            if "key" not in item or "value" not in item:
                logger.debug(f"Skipping item without key/value at index {i}: {list(item.keys())}")
                continue
            
            importance = item.get("importance", 5)
            if importance < self.min_importance:
                continue
            
            try:
                facts.append(Fact(
                    key=str(item["key"]),
                    value=str(item["value"]),
                    importance=min(importance, 10),
                    extracted_at=now,
                    source="llm"
                ))
            except Exception as e:
                logger.warning(f"Error creating Fact at index {i}: {e}")
                continue

        logger.debug(f"Parsed {len(facts)} facts from response")
        return facts[:self.max_facts]

    def _try_fix_json(self, text: str) -> Optional[list]:
        """Attempt to fix truncated JSON."""
        try:
            fixed = text.strip()
            # Remove trailing commas
            while fixed and fixed[-1] in ', \n':
                fixed = fixed[:-1]
            # Close brackets
            open_brackets = fixed.count('[') - fixed.count(']')
            open_braces = fixed.count('{') - fixed.count('}')
            fixed += ']' * open_brackets
            fixed += '}' * open_braces
            return json.loads(fixed)
        except Exception:
            return None
