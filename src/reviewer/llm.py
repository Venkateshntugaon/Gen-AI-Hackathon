"""One place for every Gemini call: prompt loading, JSON output, disk cache and retry.

Why this file exists: all LLM steps (judge, generate, verify) need the same things:
  - fill a prompt file from prompts/ with the question data,
  - ask Gemini for JSON that matches a Pydantic schema, and validate the reply,
  - cache replies on disk (data/cache/llm_cache.json) so the free-tier quota is
    saved and a live demo is instant and repeatable,
  - retry on rate-limit / server errors (wait 2 s, 4 s, 8 s), then give a clear message.
"""

import hashlib
import json
import time
from pathlib import Path

from google import genai
from google.genai import errors, types
from pydantic import TypeAdapter

from src.reviewer import config

PROMPTS_DIR = config.PROJECT_ROOT / "prompts"
CACHE_FILE = config.PROJECT_ROOT / "data" / "cache" / "llm_cache.json"
RETRY_WAITS = [2, 4, 8]   # seconds
BUSY_MESSAGE = "Gemini is busy (free-tier limit). Wait a minute and press Retry."

_client: genai.Client | None = None


class GeminiBusyError(RuntimeError):
    """Raised when Gemini keeps refusing after all retries."""


def call_json(prompt_name: str, payload: dict, schema, temperature: float = 0.2):
    """Fill prompts/<prompt_name>.md with payload, call Gemini, return a parsed schema object.

    `schema` is a Pydantic model (or a type such as list[Model]).
    """
    prompt = fill_prompt(prompt_name, payload)
    key = _cache_key(prompt, temperature)
    cache = _load_cache()
    if key not in cache:
        cache[key] = _generate_with_retry(prompt, schema, temperature)
        _save_cache(cache)
    return TypeAdapter(schema).validate_json(cache[key])


def fill_prompt(prompt_name: str, payload: dict) -> str:
    """Replace each {name} in the prompt file with payload[name].

    Plain replacement (not str.format) so other braces in a prompt are left alone.
    """
    prompt = (PROMPTS_DIR / f"{prompt_name}.md").read_text(encoding="utf-8")
    for name, value in payload.items():
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        prompt = prompt.replace("{" + name + "}", text)
    return prompt


def _generate_with_retry(prompt: str, schema, temperature: float) -> str:
    for wait in [*RETRY_WAITS, None]:
        try:
            response = _get_client().models.generate_content(
                model=config.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    response_mime_type="application/json",
                    response_schema=schema,
                ),
            )
            return response.text
        except errors.APIError as error:
            retryable = isinstance(error, errors.ServerError) or error.code == 429
            if not retryable:
                raise
            if wait is None:
                raise GeminiBusyError(BUSY_MESSAGE) from error
            time.sleep(wait)


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=config.get_api_key())
    return _client


def _cache_key(prompt: str, temperature: float) -> str:
    # The filled prompt already contains the payload, so model + prompt + payload are all covered.
    raw = f"{config.GEMINI_MODEL}\n{temperature}\n{prompt}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _load_cache() -> dict:
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    return {}


def _save_cache(cache: dict) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
