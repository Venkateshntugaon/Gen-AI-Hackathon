"""One place for every Gemini call: prompt loading, JSON output, disk cache and retry.

Why this file exists: all LLM steps (judge, generate, verify) need the same things:
  - fill a prompt file from prompts/ with the question data,
  - ask Gemini for JSON that matches a Pydantic schema, and validate the reply,
  - cache replies on disk (data/cache/llm_cache.json) so the free-tier quota is
    saved and a live demo is instant and repeatable,
  - retry on rate-limit / server errors (wait 2 s, 4 s, 8 s), then give a clear message.
    The free tier allows only a few requests per minute, so when Gemini says how long
    to wait (429 "retry in N s"), we wait that long instead (at most ~1 minute).
"""

import hashlib
import json
import re
import time
from pathlib import Path

from google import genai
from google.genai import errors, types
from pydantic import TypeAdapter

from src.reviewer import config

PROMPTS_DIR = config.PROJECT_ROOT / "prompts"
CACHE_FILE = config.PROJECT_ROOT / "data" / "cache" / "llm_cache.json"
RETRY_WAITS = [2, 4, 8]   # seconds, for server errors
MAX_RATE_LIMIT_WAIT = 65  # seconds; free-tier limits are per minute
MAX_ATTEMPTS = 6
BUSY_MESSAGE = "Gemini is busy (free-tier limit). Wait a minute and press Retry."
DAILY_LIMIT_MESSAGE = ("Gemini's free daily limit for this model is used up. Try again tomorrow, "
                       "or put another model name in GEMINI_MODEL in .env (see scripts/check_setup.py).")

_client: genai.Client | None = None


class GeminiBusyError(RuntimeError):
    """Raised when Gemini keeps refusing after all retries."""


def call_json(prompt_name: str, payload: dict, schema, temperature: float = 0.2):
    """Fill prompts/<prompt_name>.md with payload, call Gemini, return a parsed schema object.

    `schema` is a Pydantic model (or a type such as list[Model]).
    """
    _, raw = call_raw(prompt_name, payload, schema, temperature)
    return TypeAdapter(schema).validate_json(raw)


def call_raw(prompt_name: str, payload: dict, schema, temperature: float = 0.2) -> tuple[str, str]:
    """Same as call_json, but return (filled prompt, raw JSON text). Used for the report samples."""
    prompt = fill_prompt(prompt_name, payload)
    key = _cache_key(prompt, temperature)
    cache = _load_cache()
    if key not in cache:
        cache[key] = generate_text(prompt, schema, temperature)
        _save_cache(cache)
    return prompt, cache[key]


def fill_prompt(prompt_name: str, payload: dict) -> str:
    """Replace each {name} in the prompt file with payload[name].

    Plain replacement (not str.format) so other braces in a prompt are left alone.
    """
    prompt = (PROMPTS_DIR / f"{prompt_name}.md").read_text(encoding="utf-8")
    for name, value in payload.items():
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        prompt = prompt.replace("{" + name + "}", text)
    return prompt


def generate_text(prompt, schema, temperature: float) -> str:
    """Call Gemini (JSON output matching schema) with retry; no cache. Returns the raw JSON text.

    `prompt` is a string, or a list of parts (e.g. text + PDF bytes for a scanned paper).
    """
    for attempt in range(MAX_ATTEMPTS):
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
            if error.code == 429 and "per day" in str(error):
                raise GeminiBusyError(DAILY_LIMIT_MESSAGE) from error   # waiting will not help
            wait = _retry_wait(error, attempt)
            if wait is None:
                raise
            if attempt == MAX_ATTEMPTS - 1:
                raise GeminiBusyError(BUSY_MESSAGE) from error
            time.sleep(wait)
    raise GeminiBusyError(BUSY_MESSAGE)


def _retry_wait(error: errors.APIError, attempt: int) -> float | None:
    """Seconds to wait before retrying, or None if the error is not worth retrying."""
    if error.code == 429:
        suggested = re.search(r"retry in ([\d.]+)s", str(error))
        if suggested:
            return min(float(suggested.group(1)) + 1, MAX_RATE_LIMIT_WAIT)
        return RETRY_WAITS[min(attempt, len(RETRY_WAITS) - 1)] * 4
    if isinstance(error, errors.ServerError):
        return RETRY_WAITS[min(attempt, len(RETRY_WAITS) - 1)]
    return None


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
