# Note: We use the Gemini REST API directly instead of the SDK
# This provides better control over safety settings and error handling
from openai import OpenAI
from typing import Optional, Dict, Any
import requests

from app.config import settings


class LLMService:
    def __init__(self):
        self.provider = settings.llm_provider
        self.safety_settings = None  # Not needed for REST API

        # Gemini uses REST API directly - no SDK initialization needed
        # Safety settings are applied in the REST API calls

        # Initialize OpenAI
        if self.provider == "openai" and settings.openai_api_key:
            self.openai_client = OpenAI(api_key=settings.openai_api_key)
    
    def _get_style_instructions(self, note_style: str) -> Dict[str, Any]:
        """
        Get style-specific instructions for note generation.
        
        Args:
            note_style: 'short', 'moderate', or 'descriptive'
        
        Returns:
            Dict with instructions and max_tokens for the style
        """
        styles = {
            'short': {
                'instruction': """Create SHORT, easy-to-read notes:
- Use bullet points only
- Include ONLY the most important facts
- Keep each point to one simple sentence
- Focus on key takeaways
- Maximum 5-7 bullet points per section
- Use simple, everyday words
- Skip minor details""",
                'max_tokens': settings.gemini_max_output_tokens  # Use max tokens - model will follow style instructions
            },
            'moderate': {
                'instruction': """Create BALANCED, clear notes:
- Mix bullet points and short paragraphs
- Include main ideas and important details
- Explain concepts in simple terms
- Add brief examples when helpful
- Organize by topics/sections
- Use easy-to-understand language
- Keep explanations brief but clear""",
                'max_tokens': settings.gemini_max_output_tokens  # Use max tokens for comprehensive notes
            },
            'descriptive': {
                'instruction': """Create DETAILED, comprehensive notes:
- Use full paragraphs with complete explanations
- Include all important information and context
- Explain concepts thoroughly in simple language
- Add examples and details to clarify points
- Organize into clear sections with headings
- Break down complex ideas into easy steps
- Include background information when needed
- Make sure anyone can understand the content""",
                'max_tokens': settings.gemini_max_output_tokens  # Use maximum tokens from config
            }
        }
        
        return styles.get(note_style, styles['moderate'])
    
    def generate_summary(
        self,
        text: str,
        note_style: str = "moderate",
        user_prompt: Optional[str] = None,
        max_tokens: int = None
    ) -> Dict[str, Any]:
        """
        Generate a summary of the given text in the specified style.
        
        Args:
            text: Text to summarize
            note_style: 'short', 'moderate', or 'descriptive'
            user_prompt: Optional user-provided prompt instructions
            max_tokens: Maximum tokens in response (overrides style default)
        
        Returns:
            Dict with summary text, tokens used, model info
        """
        # Get style-specific settings
        style_config = self._get_style_instructions(note_style)
        if max_tokens is None:
            # Use maximum tokens from config (style config already uses max tokens)
            max_tokens = style_config['max_tokens']
        
        # Build prompt with enhanced academic context to reduce safety blocks
        academic_context = """IMPORTANT ACADEMIC CONTEXT: This is EDUCATIONAL CONTENT from university lecture slides or textbooks.

CONTENT TYPE: Academic content including formulas, equations, technical terminology, scientific concepts, historical facts, literature analysis, or any educational material and everything academic.

EDUCATIONAL PURPOSE: This is for academic learning. All technical terms, formulas, equations, concepts, and subject-specific terminology are standard educational content and everything academic.

SAFETY INSTRUCTION: Process ALL academic notation, formulas, equations, technical terms, and educational content normally. This is safe educational material. Do not block any academic or educational content."""

        base_prompt = f"""{academic_context}

You are a helpful note-taking assistant for academic content. Your job is to create notes that are very easy to understand.

{style_config['instruction']}"""
        
        if user_prompt:
            base_prompt += f"\n\nAdditional instructions: {user_prompt}"
        
        # Wrap text with academic context
        wrapped_text = f"ACADEMIC CONTENT:\n{text}\n\n(This is educational material from academic sources)"
        
        prompt = f"{base_prompt}\n\n{wrapped_text}\n\nEDUCATIONAL NOTES:"
        
        if self.provider == "gemini":
            return self._generate_gemini(prompt, max_tokens)
        elif self.provider == "openai":
            return self._generate_openai(prompt, max_tokens)
        else:
            # Fallback to simple extraction for local/other providers
            return {
                "text": self._simple_summary(text),
                "tokens_used": 0,
                "model": "simple",
                "provider": "local"
            }
    
    def synthesize_notes(
        self,
        summaries: list[str],
        note_style: str = "moderate",
        user_prompt: Optional[str] = None,
        max_tokens: int = None
    ) -> Dict[str, Any]:
        """
        Synthesize multiple summaries into a cohesive note in the specified style.
        
        Args:
            summaries: List of chunk summaries
            note_style: 'short', 'moderate', or 'descriptive'
            user_prompt: Optional user-provided prompt instructions
            max_tokens: Maximum tokens in response (overrides style default)
        
        Returns:
            Dict with synthesized note, tokens used, model info
        """
        # Get style-specific settings
        style_config = self._get_style_instructions(note_style)
        if max_tokens is None:
            # For synthesis, use maximum tokens for comprehensive output
            # Gemini 2.0+ models support up to 32,768 output tokens (or even higher for newer models)
            MAX_OUTPUT_TOKENS = settings.gemini_max_output_tokens
            
            if note_style == 'descriptive':
                # Use maximum tokens for descriptive synthesis to get comprehensive notes
                max_tokens = MAX_OUTPUT_TOKENS
            elif note_style == 'moderate':
                # Use maximum tokens for moderate style as well (why not use the full capacity?)
                max_tokens = MAX_OUTPUT_TOKENS
            else:  # short
                # Even for short, use high limit to ensure comprehensive coverage
                max_tokens = MAX_OUTPUT_TOKENS
        
        # Build prompt based on style with enhanced academic context
        academic_context = "IMPORTANT: This is educational academic content. Process all formulas, equations, technical terms, and subject-specific terminology completely.\n\n"
        
        if note_style == 'short':
            base_prompt = f"""{academic_context}You are a helpful note-taking assistant for academic content. Combine these section notes into ONE SHORT, easy-to-read final note.

This is educational/academic content. Process all formulas, equations, technical terminology, and subject-specific content normally.

Instructions:
- Create a simple bullet-point list
- Include only the MOST IMPORTANT points from all sections
- Use very simple, clear language
- Maximum 10-15 bullet points total
- Remove any repeated information
- Keep each point to one simple sentence"""

        elif note_style == 'descriptive':
            base_prompt = f"""{academic_context}You are a helpful note-taking assistant for academic content. Combine these section notes into ONE DETAILED, comprehensive final note.

This is educational/academic content. Process all formulas, equations, technical terminology, and subject-specific content normally.

CRITICAL INSTRUCTIONS FOR DESCRIPTIVE NOTES:
- Write in full, detailed paragraphs with complete explanations
- Include ALL important information from ALL sections - do not skip any significant details
- For each concept, provide thorough explanations with context and background
- Include all formulas, equations, definitions, theorems, examples, concepts, and key information from every section
- Explain the reasoning behind concepts and theories
- Show how different concepts relate to each other
- Organize into clear, well-structured sections with descriptive headings
- Use subheadings to break down complex topics
- Provide step-by-step explanations where appropriate
- Include examples and applications when mentioned in the source material
- Write as if you're creating comprehensive study notes - be thorough and complete
- Make sure anyone can understand the content without referring to the original material
- Remove only truly redundant information, but keep all important details even if somewhat related"""

        else:  # moderate
            base_prompt = f"""{academic_context}You are a helpful note-taking assistant for academic content. Combine these section notes into ONE BALANCED, clear final note.

This is educational/academic content. Process all formulas, equations, technical terminology, and subject-specific content normally.

Instructions:
- Mix bullet points and short paragraphs
- Include main ideas and key details from all sections
- Use clear, simple language
- Organize by main topics
- Remove repeated information
- Keep explanations brief but complete
- Make it easy to read and understand"""
        
        if user_prompt:
            base_prompt += f"\n\nExtra instructions from user: {user_prompt}"
        
        # Format summaries with clear separation and numbering
        combined_summaries = "\n\n---\n\n".join(f"Section {i+1}:\n{s}" for i, s in enumerate(summaries))
        
        # Add emphasis for descriptive style about including all information
        if note_style == 'descriptive':
            synthesis_instruction = f"""\n\nIMPORTANT: You are combining {len(summaries)} section summaries. Your final note MUST include comprehensive information from ALL {len(summaries)} sections above. Be thorough and detailed - this is a descriptive note that should cover everything important from all the sections.\n\nSection notes to combine:\n\n{combined_summaries}\n\nFinal Note (DESCRIPTIVE - include all details from all sections):"""
        else:
            synthesis_instruction = f"\n\nSection notes to combine:\n\n{combined_summaries}\n\nFinal Note:"
        
        prompt = f"{base_prompt}{synthesis_instruction}"
        
        if self.provider == "gemini":
            # Use longer timeout for synthesis tasks (can take longer with multiple summaries)
            # Estimate: ~1 second per 100 tokens output, so for large max_tokens, use proportional timeout
            synthesis_timeout = max(120, int(max_tokens / 50))  # At least 2 minutes, or 1s per 50 tokens
            synthesis_timeout = min(synthesis_timeout, 300)  # Cap at 5 minutes
            return self._generate_gemini(prompt, max_tokens, timeout=synthesis_timeout)
        elif self.provider == "openai":
            return self._generate_openai(prompt, max_tokens)
        else:
            return {
                "text": "\n\n".join(summaries),
                "tokens_used": 0,
                "model": "simple",
                "provider": "local"
            }
    
    def answer_question(
        self,
        question: str,
        context_chunks: list[str],
        max_tokens: int = 1000
    ) -> Dict[str, Any]:
        """
        Answer a question based on provided context in simple, easy-to-understand language.
        
        Args:
            question: User question
            context_chunks: Relevant text chunks for context
            max_tokens: Maximum tokens in response
        
        Returns:
            Dict with answer, tokens used, model info
        """
        prompt = """You are a helpful assistant. Answer the question using the information provided below. 
Use simple, easy-to-understand language. If the information isn't in the sources, say so clearly.
When possible, mention which source number your answer comes from.

Sources:
"""
        for i, chunk in enumerate(context_chunks, 1):
            prompt += f"\n[Source {i}]\n{chunk}\n"
        
        prompt += f"\n\nQuestion: {question}\n\nAnswer:"
        
        if self.provider == "gemini":
            return self._generate_gemini(prompt, max_tokens)
        elif self.provider == "openai":
            return self._generate_openai(prompt, max_tokens)
        else:
            return {
                "text": "LLM provider not configured. Please set up Gemini or OpenAI.",
                "tokens_used": 0,
                "model": "none",
                "provider": "none"
            }
    
    def _generate_gemini(self, prompt: str, max_tokens: int, max_retries: int = 3, timeout: int = 60) -> Dict[str, Any]:
        """
        Generate response using Gemini REST API directly with retry logic.
        Uses REST API instead of SDK because SDK has issues applying safety_settings correctly.
        REST API handles BLOCK_NONE settings more reliably for academic content.
        
        Args:
            prompt: The prompt text
            max_tokens: Maximum tokens in response
            max_retries: Maximum number of retry attempts
            timeout: Request timeout in seconds (longer for synthesis tasks)
        """
        import time
        
        # Use REST API directly as primary method (SDK has issues with safety_settings)
        # The REST API handles BLOCK_NONE settings more reliably for academic content
        for attempt in range(max_retries):
            try:
                return self._generate_gemini_rest_api(prompt, max_tokens, timeout)
                
            except Exception as e:
                error_str = str(e).lower()
                original_error = str(e)
                
                # Handle timeout errors - retry with exponential backoff
                if "timeout" in error_str or "read timed out" in error_str or "timed out" in error_str:
                    if attempt < max_retries - 1:
                        # For timeout, increase timeout on retry (especially for long operations)
                        retry_timeout = min(timeout * 1.5, 300)  # Increase by 50% but cap at 5 minutes
                        wait_time = min(5 * (attempt + 1), 20)  # Exponential backoff: 5s, 10s, 15s
                        print(f"Request timed out after {timeout}s, retrying with {retry_timeout}s timeout in {wait_time}s...")
                        time.sleep(wait_time)
                        timeout = int(retry_timeout)
                        continue
                    raise Exception(
                        f"Gemini API request timed out after {max_retries} retries. "
                        f"The request took longer than {timeout} seconds. This might indicate a very long prompt or slow API response. "
                        f"Error: {str(e)}"
                    )
                
                # Handle rate limiting (429 errors)
                if "429" in error_str or "quota" in error_str or "rate limit" in error_str:
                    if attempt < max_retries - 1:
                        # Extract retry delay from error if available
                        # Adjust default based on model type
                        model_name = settings.gemini_model.lower()
                        if "flash" in model_name:
                            retry_delay = 40  # Flash: 10 req/min, wait 40 seconds is safe
                        else:
                            retry_delay = 50  # Pro: 2 req/min, need at least 30s, use 50 for safety
                        
                        # Try to extract delay from error message - look for "retry in" or "seconds" patterns
                        import re
                        # Patterns to match "Please retry in 33.19s." or "retry in 33 seconds" etc.
                        delay_patterns = [
                            r'retry\s+in\s+(\d+(?:\.\d+)?)\s*s\.?',  # "retry in 33.19s" or "retry in 33.19s."
                            r'retry\s+in\s+(\d+(?:\.\d+)?)',  # "retry in 33.19"
                            r'retry_delay\s*\{\s*seconds\s*:\s*(\d+)',  # retry_delay { seconds: 33 }
                            r'(\d+(?:\.\d+)?)\s*seconds',  # "33 seconds"
                        ]
                        
                        for pattern in delay_patterns:
                            delay_match = re.search(pattern, original_error, re.IGNORECASE)
                            if delay_match:
                                extracted_delay = float(delay_match.group(1))
                                # Add buffer based on model type
                                if "flash" in model_name:
                                    retry_delay = max(extracted_delay + 5, 35)  # At least 35 seconds for Flash
                                else:
                                    retry_delay = max(extracted_delay + 10, 45)  # At least 45 seconds for Pro
                                break
                        
                        print(f"Rate limit hit, waiting {retry_delay:.1f} seconds before retry {attempt + 1}/{max_retries}")
                        time.sleep(retry_delay)
                        continue
                    raise Exception(
                        f"Gemini API rate limit exceeded after {max_retries} retries. "
                        f"Free tier allows 2 requests/minute. Please wait longer or upgrade your plan. "
                        f"Error: {str(e)}"
                    )
                else:
                    # Check if error is due to MAX_TOKENS with no parts (prompt too long)
                    # This can be either a ValueError with "TOKEN_LIMIT_NO_CONTENT" or an error message about token limits
                    is_token_limit_error = (
                        "TOKEN_LIMIT_NO_CONTENT" in error_str or
                        "token limit before generating" in error_str or 
                        ("max_tokens" in error_str and "prompt" in error_str.lower())
                    )
                    
                    if is_token_limit_error:
                        # This means the prompt is too long - try reducing input text
                        if attempt < max_retries - 1:
                            # Truncate the prompt by reducing the input text portion
                            # The prompt format is: academic_context + instructions + "\n\n" + wrapped_text + "\n\nEDUCATIONAL NOTES:"
                            # Find where the input text starts and truncate it
                            if "ACADEMIC CONTENT:\n" in prompt:
                                parts = prompt.split("ACADEMIC CONTENT:\n", 1)
                                if len(parts) == 2:
                                    base_prompt = parts[0] + "ACADEMIC CONTENT:\n"
                                    input_text_section = parts[1]
                                    # Find where the actual text ends (before the closing note)
                                    if "\n\n(This is educational" in input_text_section:
                                        text_parts = input_text_section.split("\n\n(This is educational", 1)
                                        actual_text = text_parts[0]
                                        rest = "\n\n(This is educational" + text_parts[1] if len(text_parts) > 1 else ""
                                        
                                        # Truncate text to 70% of original length
                                        truncated_length = int(len(actual_text) * 0.7)
                                        truncated_text = actual_text[:truncated_length] + "...\n[Content truncated due to length]"
                                        
                                        prompt = base_prompt + truncated_text + rest
                                        print(f"Retry {attempt + 1}: Truncated input text from {len(actual_text)} to {len(truncated_text)} characters due to token limit")
                                        time.sleep(1)
                                        continue
                            # If we can't truncate (e.g., synthesis prompts), try reducing max_tokens significantly
                            # For synthesis, we might need to reduce max_output_tokens more aggressively
                            if max_tokens > 5000:
                                max_tokens = int(max_tokens * 0.5)  # Reduce by 50%
                                print(f"Retry {attempt + 1}: Reduced max_tokens to {max_tokens} due to token limit")
                                time.sleep(1)
                                continue
                    
                    # For other errors, re-raise immediately if it's a safety block or similar
                    if attempt < max_retries - 1 and "safety" not in error_str.lower() and "recitation" not in error_str.lower():
                        time.sleep(2 ** attempt)  # Exponential backoff for other errors
                        continue
                    raise Exception(f"Gemini API error: {str(e)}")
        
        raise Exception(f"Gemini API failed after {max_retries} attempts")
    
    def _generate_gemini_rest_api(self, prompt: str, max_tokens: int, timeout: int = 60) -> Dict[str, Any]:
        """
        Use REST API directly to call Gemini API.
        This method handles BLOCK_NONE safety settings more reliably than the SDK
        for academic content, and properly accepts MAX_TOKENS responses.
        
        Args:
            prompt: The prompt text
            max_tokens: Maximum tokens in response
            timeout: Request timeout in seconds (default 60, use longer for synthesis tasks)
        """
        import json
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"
        headers = {
            "x-goog-api-key": settings.gemini_api_key,
            "Content-Type": "application/json"
        }
        
        # Build safety settings for REST API (BLOCK_NONE = 0)
        safety_settings_rest = [
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        
        # Estimate prompt token count (rough approximation: 1 token ≈ 4 characters)
        # Gemini models have total context limits, so we need to ensure prompt + output fits
        prompt_token_estimate = len(prompt) // 4
        
        # For Gemini Flash models: total context ~1M tokens
        # Reserve space for the output, but don't exceed reasonable limits
        # If prompt is very long, reduce maxOutputTokens to fit within context
        MAX_CONTEXT_TOKENS = 1000000  # Gemini 2.5 Flash approximate context window
        SAFE_BUFFER = 50000  # Increased buffer to ensure we have room
        available_for_output = MAX_CONTEXT_TOKENS - prompt_token_estimate - SAFE_BUFFER
        
        # Use the minimum of: requested max_tokens, available space, and model limit
        # Gemini Flash supports up to 8192 output tokens by default, but newer models might support more
        # However, if prompt is long, we need to reduce output tokens
        # Be more aggressive: ensure we have at least some room for output
        MIN_OUTPUT_TOKENS = 500  # Minimum output tokens we need
        effective_max_tokens = min(
            max_tokens,
            max(MIN_OUTPUT_TOKENS, available_for_output),  # At least MIN_OUTPUT_TOKENS, but respect available space
            55000  # Hard cap for most Gemini models
        )
        
        # If prompt is extremely long and we can't generate even minimum output, warn and reduce more
        if available_for_output < MIN_OUTPUT_TOKENS:
            # Prompt is too long - we need to reduce output tokens to minimum
            effective_max_tokens = MIN_OUTPUT_TOKENS
            print(f"WARNING: Prompt is very long ({prompt_token_estimate} estimated tokens). "
                  f"Only {available_for_output} tokens available for output. "
                  f"Setting maxOutputTokens to minimum {MIN_OUTPUT_TOKENS}.")
        elif effective_max_tokens < max_tokens:
            print(f"WARNING: Prompt is long ({prompt_token_estimate} estimated tokens). "
                  f"Reducing maxOutputTokens from {max_tokens} to {effective_max_tokens} to fit context.")
        
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "maxOutputTokens": effective_max_tokens,
                "temperature": 1.0
            },
            "safetySettings": safety_settings_rest
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=timeout)
        
        # Debug: Log response status for troubleshooting
        if response.status_code != 200:
            print(f"DEBUG: Gemini API returned status {response.status_code}")
            print(f"DEBUG: Response text: {response.text[:500]}")  # First 500 chars
        
        # Check for HTTP errors
        if response.status_code != 200:
            try:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", str(response.status_code))
                raise Exception(f"Gemini API HTTP error {response.status_code}: {error_msg}")
            except:
                raise Exception(f"Gemini API HTTP error {response.status_code}: {response.text}")
        
        try:
            data = response.json()
        except Exception as json_error:
            print(f"DEBUG: Failed to parse JSON response. Status: {response.status_code}")
            print(f"DEBUG: Response text: {response.text[:1000]}")  # First 1000 chars
            raise Exception(f"Failed to parse Gemini API JSON response: {str(json_error)}")
        
        # Debug: Log response structure for troubleshooting
        if "candidates" not in data:
            print(f"DEBUG: Response missing 'candidates'. Keys: {list(data.keys())}")
            print(f"DEBUG: Full response: {json.dumps(data, indent=2)[:2000]}")  # First 2000 chars
        
        # Check for errors in response body (even if HTTP status is 200)
        if "error" in data:
            error_info = data["error"]
            error_msg = error_info.get("message", "Unknown error")
            error_code = error_info.get("code", "UNKNOWN")
            raise Exception(f"Gemini API error in response: {error_code} - {error_msg}")
        
        if "candidates" not in data or not data["candidates"]:
            # Check for promptFeedback which might indicate blocking
            if "promptFeedback" in data:
                feedback = data["promptFeedback"]
                block_reason = feedback.get("blockReason")
                if block_reason:
                    raise Exception(
                        f"Gemini API blocked prompt: {block_reason}. "
                        f"Feedback: {json.dumps(feedback, indent=2)}"
                    )
            raise Exception(
                f"No candidates in REST API response. "
                f"Response structure: {json.dumps(data, indent=2)}"
            )
        
        candidate = data["candidates"][0]
        
        
        # Check if candidate has an error instead of content
        if "error" in candidate:
            error_info = candidate["error"]
            error_msg = error_info.get("message", "Unknown error")
            raise Exception(f"Gemini API candidate error: {error_msg}")
        
        finish_reason = candidate.get("finishReason")
        
        # MAX_TOKENS means response was truncated but is still valid - accept it
        if finish_reason and finish_reason not in ["STOP", "MAX_TOKENS"]:
            raise Exception(f"REST API also blocked: finishReason={finish_reason}")
        
        # Safely access the text content with proper error handling
        if "content" not in candidate:
            # Log the full candidate structure for debugging
            raise Exception(
                f"No 'content' in candidate. Response structure: {json.dumps(candidate, indent=2)}"
            )
        
        content = candidate["content"]
        
        # Ensure content is a dict
        if not isinstance(content, dict):
            print(f"DEBUG: Content is not a dict. Type: {type(content)}, Value: {content}")
            raise Exception(
                f"Content is not a dict. Type: {type(content)}, Value: {json.dumps(content, indent=2)}, "
                f"Full candidate: {json.dumps(candidate, indent=2)}"
            )
        
        # Check if content has parts
        # Handle edge case where content only has "role" field (malformed response from API)
        if "parts" not in content or not content.get("parts"):
            # This can happen when finishReason is MAX_TOKENS but no content was generated
            # This might be due to prompt being too long or hitting token limit immediately
            print(f"DEBUG: Content keys: {list(content.keys())}")
            print(f"DEBUG: Full content: {json.dumps(content, indent=2)}")
            print(f"DEBUG: Full candidate: {json.dumps(candidate, indent=2)}")
            
            # If finishReason is MAX_TOKENS and no parts exist, the prompt might be too long
            if finish_reason == "MAX_TOKENS":
                # Calculate prompt length for better error message
                prompt_len = len(prompt)
                prompt_tokens_est = prompt_len // 4
                # Raise a specific exception that the retry logic can catch
                raise ValueError(
                    f"TOKEN_LIMIT_NO_CONTENT: Response hit token limit before generating any content. "
                    f"Prompt is {prompt_len} characters (~{prompt_tokens_est} tokens), which is too long. "
                    f"The input chunk text might be too large, or the prompt instructions are too verbose."
                )
            else:
                raise Exception(
                    f"No 'parts' in content. Content structure: {json.dumps(content, indent=2)}, "
                    f"Full candidate: {json.dumps(candidate, indent=2)}"
                )
        
        # Safely access parts
        try:
            parts = content["parts"]
        except KeyError as e:
            print(f"DEBUG: KeyError accessing 'parts'. Content keys: {list(content.keys())}")
            print(f"DEBUG: Full content: {json.dumps(content, indent=2)}")
            raise Exception(
                f"KeyError accessing 'parts': {str(e)}. Content structure: {json.dumps(content, indent=2)}, "
                f"Full candidate: {json.dumps(candidate, indent=2)}"
            ) from e
        if not parts or len(parts) == 0:
            raise Exception(
                f"Empty 'parts' array. Content structure: {json.dumps(content, indent=2)}"
            )
        
        if "text" not in parts[0]:
            raise Exception(
                f"No 'text' in first part. Parts structure: {json.dumps(parts, indent=2)}"
            )
        
        text = parts[0]["text"]
        
        if finish_reason == "MAX_TOKENS":
            print(f"REST API response truncated at token limit (this is acceptable)")
        
        usage = data.get("usageMetadata", {})
        tokens_used = usage.get("totalTokenCount", 0)
        
        return {
            "text": text,
            "tokens_used": tokens_used,
            "model": settings.gemini_model,
            "provider": "gemini"
        }
    
    def _generate_openai(self, prompt: str, max_tokens: int) -> Dict[str, Any]:
        """Generate response using OpenAI."""
        try:
            response = self.openai_client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=0.7
            )
            
            return {
                "text": response.choices[0].message.content,
                "tokens_used": response.usage.total_tokens,
                "model": settings.openai_model,
                "provider": "openai"
            }
        except Exception as e:
            raise Exception(f"OpenAI API error: {str(e)}")
    
    def _simple_summary(self, text: str, max_sentences: int = 5) -> str:
        """Simple extractive summary (fallback)."""
        import nltk
        sentences = nltk.sent_tokenize(text)
        # Return first few sentences as summary
        return " ".join(sentences[:max_sentences])


# Global LLM service instance
llm_service = LLMService()
