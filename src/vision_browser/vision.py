"""Vision model clients — NIM (primary) + Groq (fallback) with retry and rate limiting."""

from __future__ import annotations

import base64
import json
import logging
import time
from pathlib import Path

import httpx
from groq import Groq

from vision_browser.config import VisionConfig
from vision_browser.exceptions import (
    ModelResponseError,
    RateLimitError,
    TimeoutError,
    VisionAPIError,
)

logger = logging.getLogger(__name__)


class VisionClient:
    """Unified vision model interface with retry, rate limiting, and fallback."""

    def __init__(self, cfg: VisionConfig, orchestrator_cfg: dict | None = None):
        self.cfg = cfg
        self.orchestrator_cfg = orchestrator_cfg or {}
        self._max_retries = self.orchestrator_cfg.get("retry_attempts", 3)
        self._backoff_base = self.orchestrator_cfg.get("retry_backoff_base", 1.0)
        self._rate_delay = self.orchestrator_cfg.get("rate_limit_delay", 0.5)
        self._last_request_time = 0.0
        self._groq: Groq | None = None

    def analyze(self, image_path: str, prompt: str, schema: dict | None = None) -> dict:
        """Send image + prompt to vision model. Retry with backoff + fallback."""
        for attempt in range(1, self._max_retries + 1):
            # Rate limiting
            self._apply_rate_limit()

            try:
                return self._nim_analyze(image_path, prompt, schema)
            except ModelResponseError:
                # Model returned invalid JSON -- retry with stricter prompt
                if attempt < self._max_retries:
                    stricter_prompt = self._build_stricter_prompt(prompt, schema, attempt)
                    logger.warning(f"JSON parse failed on attempt {attempt}, retrying with stricter prompt")
                    try:
                        return self._nim_analyze(image_path, stricter_prompt, schema)
                    except ModelResponseError:
                        pass  # Fall through to fallback
                # Try Groq as fallback
                try:
                    return self._groq_analyze(image_path, prompt, schema)
                except Exception as ge:
                    logger.warning(f"Groq fallback also failed: {ge}")

                if attempt == self._max_retries:
                    raise VisionAPIError(
                        "All vision API attempts exhausted. Last error: model failed to produce valid JSON after retries"
                    )

                backoff = self._backoff_base * (2 ** (attempt - 1))
                logger.info(f"Retrying in {backoff:.1f}s...")
                time.sleep(backoff)
            except Exception as e:
                logger.warning(f"NIM attempt {attempt} failed: {e}")
                if attempt < self._max_retries:
                    # Try Groq as fallback before retrying NIM
                    try:
                        return self._groq_analyze(image_path, prompt, schema)
                    except Exception as ge:
                        logger.warning(f"Groq fallback also failed: {ge}")

                if attempt == self._max_retries:
                    raise VisionAPIError(
                        f"All vision API attempts exhausted. Last error: {e}"
                    ) from e

                backoff = self._backoff_base * (2 ** (attempt - 1))
                logger.info(f"Retrying in {backoff:.1f}s...")
                time.sleep(backoff)

        # Should never reach here
        raise VisionAPIError("Unexpected: analyze loop exited without returning or raising")

    def _apply_rate_limit(self) -> None:
        """Enforce minimum delay between requests."""
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < self._rate_delay:
            sleep_time = self._rate_delay - elapsed
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        self._last_request_time = time.monotonic()

    def _get_groq(self) -> Groq:
        if self._groq is None:
            api_key = self.cfg.groq_api_key
            if not api_key:
                raise VisionAPIError("GROQ_API_KEY not set")
            self._groq = Groq(api_key=api_key)
        return self._groq

    def _groq_analyze(self, image_path: str, prompt: str, schema: dict | None = None) -> dict:
        """Call Groq vision API with optional JSON schema enforcement."""
        logger.debug("Calling Groq vision API")
        client = self._get_groq()
        image_b64 = self._encode_image(image_path)

        try:
            kwargs = {
                "model": self.cfg.groq_model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_b64}",
                                },
                            },
                        ],
                    }
                ],
                "max_tokens": self.cfg.groq_max_tokens,
                "temperature": 0.1,
            }
            
            # Use function calling if schema provided, otherwise json_object
            if schema:
                kwargs["tools"] = [{
                    "type": "function",
                    "function": {
                        "name": "browser_action",
                        "description": "Execute browser automation actions",
                        "parameters": schema,
                        "strict": True,
                    }
                }]
                kwargs["tool_choice"] = {"type": "function", "function": {"name": "browser_action"}}
            else:
                kwargs["response_format"] = {"type": "json_object"}

            response = client.chat.completions.create(**kwargs)
        except Exception as e:
            if "429" in str(e):
                raise RateLimitError(f"Groq rate limited: {e}") from e
            raise VisionAPIError(f"Groq API error: {e}") from e

        # Handle function calling response
        if schema and response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            try:
                return json.loads(tool_call.function.arguments)
            except json.JSONDecodeError as e:
                raise VisionAPIError(f"Groq function arguments not valid JSON: {e}") from e

        # Handle json_object response
        text = response.choices[0].message.content
        if text is None:
            raise VisionAPIError("Groq returned empty response")
        return self._validate_json_response(text.strip(), schema)

    def _nim_analyze(self, image_path: str, prompt: str, schema: dict | None = None) -> dict:
        """Call NVIDIA NIM vision API via NVCF with optional JSON schema."""
        logger.debug("Calling NIM vision API")
        image_b64 = self._encode_image(image_path)

        # Build message with schema enforcement if provided
        if schema:
            prompt = (
                f"Return ONLY valid JSON matching this schema:\n"
                f"{json.dumps(schema, indent=2)}\n\n"
                f"Task: {prompt}\n\n"
                f"Return ONLY the JSON object, no markdown, no explanation."
            )

        try:
            resp = httpx.post(
                f"https://api.nvcf.nvidia.com/v2/nvcf/pexec/functions/{self.cfg.nim_function_id}",
                headers={
                    "Authorization": f"Bearer {self.cfg.nim_api_key}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json={
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{image_b64}",
                                    },
                                },
                            ],
                        }
                    ],
                    "max_tokens": self.cfg.nim_max_tokens,
                    "temperature": 0.1,
                },
                timeout=120,
            )
        except httpx.TimeoutException as e:
            raise TimeoutError(f"NIM API timed out after 120s: {e}") from e
        except httpx.HTTPStatusError as e:
            # HTTPStatusError always has .response
            if e.response.status_code == 429:
                raise RateLimitError(f"NIM rate limited: {e}") from e
            raise VisionAPIError(f"NIM HTTP error {e.response.status_code}: {e}") from e
        except httpx.HTTPError as e:
            # Other HTTPError subclasses (ConnectError, etc.) may not have .response
            raise VisionAPIError(f"NIM HTTP error: {e}") from e

        if resp.status_code != 200:
            raise VisionAPIError(
                f"NIM API returned {resp.status_code}: {resp.text[:500]}"
            )

        try:
            data = resp.json()
        except json.JSONDecodeError as e:
            raise VisionAPIError(f"NIM returned invalid JSON: {resp.text[:500]}") from e

        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not text:
            raise VisionAPIError("NIM returned empty response")
        return self._validate_json_response(text.strip(), schema)

    @staticmethod
    def _extract_json(text: str) -> dict:
        """Extract JSON from model output — handles code blocks, loose text, etc."""
        # 1. Strip markdown code blocks
        if "```" in text:
            for block in text.split("```"):
                if block.startswith("json"):
                    block = block[4:]
                block = block.strip()
                if block.startswith("{"):
                    try:
                        return json.loads(block)
                    except json.JSONDecodeError:
                        pass

        # 2. Try direct parse
        if text.startswith("{"):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass

        # 3. Stack-based balanced brace extraction
        start = text.find("{")
        if start != -1:
            depth = 0
            for i, ch in enumerate(text[start:], start):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        candidate = text[start : i + 1]
                        try:
                            return json.loads(candidate)
                        except json.JSONDecodeError:
                            break

        # 4. Last resort: wrap text in a safe structure
        logger.warning("Could not extract JSON from model response. Wrapping text.")
        return {"actions": [], "done": False, "reasoning": text.strip()}

    def _validate_json_response(
        self, text: str, schema: dict | None = None
    ) -> dict:
        """Validate that model text can be extracted as valid JSON.

        Args:
            text: Raw model response text.
            schema: Expected JSON schema for context in error reporting.

        Returns:
            Extracted JSON dict.

        Raises:
            ModelResponseError: If text cannot be parsed as JSON.
        """
        if not text:
            raise ModelResponseError(
                "Model returned empty response",
                raw_response=text,
                expected_schema=schema,
            ).with_context(stage="empty_response")

        # Try to parse as JSON directly first
        stripped = text.strip()
        if stripped.startswith("{"):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                pass

        # Try _extract_json which handles markdown blocks and brace extraction
        result = self._extract_json(text)

        # _extract_json returns a safe wrapper when it can't find JSON.
        # The safe wrapper has reasoning that matches the original text closely.
        # Detect this by checking if reasoning is essentially the raw input text
        # (i.e., no JSON-like structure was found at all).
        reasoning = result.get("reasoning", "")
        if (
            result.get("actions") == []
            and result.get("done") is False
            and reasoning
            and reasoning.strip() == text.strip()
        ):
            # The reasoning is the entire input text -- extraction failed
            raise ModelResponseError(
                "Model response could not be parsed as JSON",
                raw_response=text[:1000],
                expected_schema=schema,
            ).with_context(stage="parse_fallback", model_text_preview=text[:200])

        return result

    @staticmethod
    def _build_stricter_prompt(original_prompt: str, schema: dict | None, attempt: int) -> str:
        """Build a progressively stricter prompt for JSON retry.

        Args:
            original_prompt: The original prompt text.
            schema: The expected JSON schema.
            attempt: Current retry attempt number (1-based).

        Returns:
            New prompt with stricter JSON requirements.
        """
        strictness = {
            1: "IMPORTANT: Your previous response was not valid JSON. You MUST respond with ONLY a JSON object, nothing else.",
            2: "CRITICAL: You MUST respond with ONLY valid JSON. No text before or after the JSON object. No markdown. No explanation. Start with { and end with }.",
        }
        prefix = strictness.get(attempt, strictness[2])
        return f"{prefix}\n\n{original_prompt}"

    @staticmethod
    def _encode_image(path: str | Path) -> str:
        """Base64-encode an image file."""
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
