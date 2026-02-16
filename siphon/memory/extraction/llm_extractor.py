"""LLM-based fact extraction with structured output validation and retry logic.

This module provides robust fact extraction from conversations using any LLM
provider through LiveKit's unified interface. It includes:
- Pydantic schema validation for type-safe outputs
- Retry logic with progressive prompt refinement
- Support for both array and object JSON formats
- Provider-agnostic extraction (works with OpenAI, Anthropic, Groq, etc.)
"""

import json
import re
from typing import Any, Dict, List, Optional
from pydantic import ValidationError

from siphon.memory.extraction.base import FactExtractor as BaseExtractor
from siphon.memory.extraction.prompts import SYSTEM_PROMPT, build_extraction_prompt
from siphon.memory.extraction.schemas import FactExtractionOutput, ExtractedFact
from siphon.memory.models import ExtractionResult, Fact
from siphon.config import get_logger

logger = get_logger("calling-agent")


class LLMFactExtractor(BaseExtractor):
    """Extract facts using an LLM with structured output validation and retry logic.
    
    This extractor works with any LLM provider (OpenAI, Anthropic, Groq, etc.) through
    LiveKit's unified interface. It validates outputs against a Pydantic schema and
    implements retry logic to handle malformed responses.
    
    Args:
        llm: The LLM instance to use for extraction (any LiveKit-compatible LLM)
        min_importance: Minimum importance score (1-10) for facts to be included
        max_facts: Maximum number of facts to extract per conversation
        max_retries: Maximum number of retry attempts for failed extractions
    """

    def __init__(
        self,
        llm: Any,
        min_importance: int = 4,
        max_facts: int = 50,
        max_retries: int = 10,
    ) -> None:
        super().__init__(min_importance, max_facts)
        self.llm = llm
        self.max_retries = max_retries

    async def extract(self, conversation_history: List[Dict[str, Any]]) -> ExtractionResult:
        """Extract facts from conversation with validation and retry logic.
        
        This method attempts to extract facts up to max_retries times, using
        progressively stricter prompts if parsing fails. Each attempt validates
        the output against the FactExtractionOutput Pydantic schema.
        
        Args:
            conversation_history: List of conversation messages with 'role' and 'content'
            
        Returns:
            ExtractionResult containing extracted facts or error information
        """
        if not conversation_history:
            logger.warning("No conversation history provided for fact extraction")
            return ExtractionResult(success=True)

        # Check if there's any user content
        has_user_content = any(
            msg.get('role') == 'user' and msg.get('content', '').strip()
            for msg in conversation_history
        )
        
        if not has_user_content:
            logger.debug("No user responses found, skipping extraction")
            return ExtractionResult(success=True)

        # Format conversation
        conversation_text = self._format_conversation(conversation_history)
        if not conversation_text.strip():
            logger.debug("Empty conversation text after formatting")
            return ExtractionResult(success=True)

        # Escape curly braces in conversation_text to prevent .format() from interpreting them
        # This is important because conversation text may contain literal braces
        safe_conversation_text = conversation_text.replace("{", "{{").replace("}", "}}")

        # Attempt extraction with retry logic
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                # Build appropriate prompt based on attempt number
                is_retry = attempt > 1
                is_final = attempt == self.max_retries
                
                prompt = build_extraction_prompt(
                    conversation_text=safe_conversation_text,
                    is_retry=is_retry,
                    error_message=str(last_error) if last_error else None,
                    is_final_attempt=is_final
                )

                logger.debug(f"Extraction attempt {attempt}/{self.max_retries}")
                
                # Extract from LLM
                result_text = await self._extract_with_llm(prompt)
                
                if not result_text:
                    logger.warning(f"Attempt {attempt}: LLM returned empty response")
                    last_error = "Empty response from LLM"
                    continue

                # Parse and validate response
                facts = self._parse_and_validate(result_text)
                
                if facts:
                    logger.info(f"Successfully extracted {len(facts)} facts on attempt {attempt}")
                    return ExtractionResult(
                        facts=facts,
                        raw_response=result_text,
                        success=True
                    )
                else:
                    # No facts found but parsing succeeded
                    logger.debug(f"No facts extracted on attempt {attempt}")
                    return ExtractionResult(
                        facts=[],
                        raw_response=result_text,
                        success=True
                    )

            except json.JSONDecodeError as e:
                last_error = f"JSON parse error: {str(e)}"
                logger.warning(f"Attempt {attempt}: {last_error}")
                if attempt < self.max_retries:
                    continue
                    
            except ValidationError as e:
                last_error = f"Validation error: {str(e)}"
                logger.warning(f"Attempt {attempt}: {last_error}")
                if attempt < self.max_retries:
                    continue
                    
            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"
                logger.error(f"Attempt {attempt}: {last_error}")
                if attempt < self.max_retries:
                    continue

        # All retries exhausted
        logger.error(f"Failed to extract facts after {self.max_retries} attempts. Last error: {last_error}")
        return ExtractionResult(
            success=False,
            error_message=last_error,
            raw_response=None
        )

    async def _extract_with_llm(self, prompt: str) -> Optional[str]:
        """Extract text using the configured LLM through LiveKit interface.
        
        This method attempts to use LiveKit's unified chat interface first,
        falling back to OpenAI-style completions if needed.
        
        Args:
            prompt: The formatted extraction prompt
            
        Returns:
            Raw text response from LLM, or None if extraction fails
        """
        # Try LiveKit LLM first (unified interface)
        if hasattr(self.llm, 'chat') and callable(getattr(self.llm, 'chat')):
            # Check if it's a LiveKit plugin LLM
            try:
                return await self._extract_with_livekit(prompt)
            except Exception as e:
                logger.debug(f"LiveKit extraction failed, trying fallback: {e}")
        
        # Try OpenAI-style interface as fallback
        if hasattr(self.llm, 'chat') and hasattr(self.llm.chat, 'completions'):
            try:
                return await self._extract_with_openai(prompt)
            except Exception as e:
                logger.debug(f"OpenAI-style extraction failed: {e}")
        
        logger.error("No compatible LLM interface found")
        return None

    async def _extract_with_livekit(self, prompt: str) -> Optional[str]:
        """Extract using LiveKit LLM's unified chat interface.
        
        This works with any LLM provider wrapped by LiveKit plugins.
        
        Args:
            prompt: The extraction prompt
            
        Returns:
            Response text from LLM
        """
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
                        chunks.append(str(content))
            
            response_text = "".join(chunks)
            logger.debug(f"LiveKit LLM collected {chunk_count} chunks, response length: {len(response_text)}")
            return response_text if response_text else None
            
        except Exception as e:
            logger.error(f"LiveKit extraction error: {e}")
            raise

    async def _extract_with_openai(self, prompt: str) -> Optional[str]:
        """Extract using OpenAI-style completions API.
        
        This is a fallback for LLMs that expose an OpenAI-compatible interface.
        
        Args:
            prompt: The extraction prompt
            
        Returns:
            Response text from LLM
        """
        try:
            response = await self.llm.chat.completions.create(
                model=getattr(self.llm, 'model', 'gpt-4o-mini'),
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000,
            )
            content = response.choices[0].message.content if response.choices else None
            logger.debug(f"OpenAI-style extraction completed, response length: {len(content) if content else 0}")
            return content
        except Exception as e:
            logger.error(f"OpenAI extraction error: {e}")
            raise

    def _parse_and_validate(self, result_text: str) -> List[Fact]:
        """Parse and validate facts from LLM response with Pydantic schema.
        
        This method:
        1. Cleans common formatting issues (markdown code blocks, extra whitespace)
        2. Parses JSON
        3. Validates against FactExtractionOutput Pydantic model
        4. Filters by importance
        5. Converts to Fact models
        
        Args:
            result_text: Raw text response from LLM
            
        Returns:
            List of validated Fact objects
            
        Raises:
            json.JSONDecodeError: If response is not valid JSON
            ValidationError: If JSON doesn't match expected schema
        """
        # Clean markdown formatting
        result_text = self._clean_response_text(result_text)

        # Parse JSON
        try:
            data = json.loads(result_text)
        except json.JSONDecodeError as e:
            # Try to fix common JSON issues
            fixed_data = self._try_fix_json(result_text)
            if fixed_data is not None:
                data = fixed_data
            else:
                raise json.JSONDecodeError(f"Invalid JSON: {e}", result_text, e.pos if hasattr(e, 'pos') else 0)

        # Handle both old format (array) and new format (object with facts key)
        if isinstance(data, list):
            # Old format: direct array of facts
            logger.debug("Parsed legacy array format")
            facts_data = {"facts": data}
        elif isinstance(data, dict):
            if "facts" in data:
                # New format: object with facts key
                facts_data = data
            elif len(data) > 0:
                # Maybe it's a single fact object, wrap it
                facts_data = {"facts": [data]}
            else:
                # Empty object
                facts_data = {"facts": []}
        else:
            raise ValidationError(f"Expected list or dict, got {type(data).__name__}")

        # Validate with Pydantic
        try:
            validated = FactExtractionOutput.model_validate(facts_data)
        except ValidationError as e:
            logger.warning(f"Schema validation failed: {e}")
            raise

        # Filter by importance and validate context, then convert to Fact models
        facts = []
        for extracted_fact in validated.facts:
            if extracted_fact.importance >= self.min_importance:
                # Validate that the fact has sufficient context
                if self._has_sufficient_context(extracted_fact):
                    fact = Fact(
                        key=extracted_fact.key,
                        value=extracted_fact.value,
                        importance=extracted_fact.importance,
                        source="llm"
                    )
                    facts.append(fact)
                else:
                    logger.warning(f"Fact '{extracted_fact.key}' rejected: insufficient context. Value: '{extracted_fact.value}'")

        logger.debug(f"Validated {len(facts)} facts (filtered from {len(validated.facts)})")
        return facts[:self.max_facts]

    def _has_sufficient_context(self, extracted_fact) -> bool:
        """Check if a fact has sufficient context.
        
        Accepts facts with descriptive values. Rejects only bare minimum facts.
        
        Args:
            extracted_fact: The extracted fact to validate
            
        Returns:
            True if fact has sufficient context, False otherwise
        """
        value = extracted_fact.value.strip()
        
        # Reject very short bare facts (less than 8 chars)
        if len(value) < 8:
            return False
        
        # Accept if has parentheses context (preferred format)
        if '(' in value and ')' in value:
            return True
        
        # Accept if has reasonable length (15+ chars) - assumes descriptive value
        if len(value) >= 15:
            return True
        
        # For very short values (8-14 chars), require context indicator
        context_indicators = ['(', ' - ', ': ', 'for', 'at', 'on', 'to']
        return any(indicator in value.lower() for indicator in context_indicators)

    def _clean_response_text(self, text: str) -> str:
        """Clean common formatting issues from LLM response.
        
        Removes markdown code blocks, extra whitespace, and common
        explanatory text that LLMs sometimes add.
        
        Args:
            text: Raw LLM response text
            
        Returns:
            Cleaned text ready for JSON parsing
        """
        text = text.strip()
        
        # Remove markdown code blocks
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        
        if text.endswith("```"):
            text = text[:-3]
        
        text = text.strip()
        
        # Remove common prefixes LLMs sometimes add
        prefixes_to_remove = [
            "Here is the extracted JSON:",
            "Here's the JSON output:",
            "Extracted facts:",
            "JSON Response:",
            "Output:",
        ]
        
        for prefix in prefixes_to_remove:
            if text.lower().startswith(prefix.lower()):
                text = text[len(prefix):].strip()
        
        return text

    def _try_fix_json(self, text: str) -> Optional[Dict]:
        """Attempt to fix common JSON formatting issues.
        
        Fixes trailing commas, missing closing brackets, unterminated strings, etc.
        This is a best-effort attempt before giving up.
        
        Args:
            text: Potentially malformed JSON string
            
        Returns:
            Parsed JSON data if fixable, None otherwise
        """
        fixed = text.strip()
        
        # Remove trailing commas (common issue)
        while fixed and fixed[-1] in ', \n\t':
            fixed = fixed[:-1]
        
        # Check for unterminated strings and close them
        # Find all unescaped double quotes
        quotes = []
        i = 0
        while i < len(fixed):
            if fixed[i] == '"':
                if i == 0 or fixed[i-1] != '\\':
                    quotes.append(i)
            i += 1
        
        # If odd number of quotes, we have an unterminated string
        if len(quotes) % 2 == 1:
            # Add closing quote
            fixed += '"'
        
        # Balance brackets and braces
        open_brackets = fixed.count('[') - fixed.count(']')
        open_braces = fixed.count('{') - fixed.count('}')
        
        # Close any open structures
        fixed += '}' * open_braces
        fixed += ']' * open_brackets
        
        # Try to parse
        try:
            return json.loads(fixed)
        except Exception:
            pass
        
        # Try aggressive extraction - look for individual fact objects
        try:
            # Find all fact objects in the text
            fact_pattern = r'\{\s*"key"\s*:\s*"([^"]+)"\s*,\s*"value"\s*:\s*"([^"]*)"\s*,\s*"importance"\s*:\s*(\d+)\s*\}'
            matches = re.findall(fact_pattern, text)
            
            if matches:
                facts = []
                for key, value, importance in matches:
                    facts.append({
                        "key": key,
                        "value": value,
                        "importance": int(importance)
                    })
                return {"facts": facts}
        except:
            pass
        
        return None
