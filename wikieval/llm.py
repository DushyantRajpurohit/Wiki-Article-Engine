"""
Gemini calls with a persistent cache, a request-rate limit and retries.

The free tier has per-minute and per-day request limits. The cache means an
interrupted run resumes where it stopped and a rerun of the report costs nothing.
"""

import hashlib
import json
import os
import re
import sqlite3
import time

from google import genai
from google.genai import errors, types

from . import config

_client = None
_last_request = 0.0


class DailyQuota(SystemExit):
    """A model's free daily requests are used up. Stops the run unless the caller can work around it."""


class Blocked(Exception):
    """The provider's safety filter refused the request. Callers record this; it is a result, not a crash."""


def client():
    global _client
    if _client is None:
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise SystemExit("Set the GEMINI_API_KEY environment variable (free key: aistudio.google.com).")
        _client = genai.Client(api_key=key)
    return _client


def _cache():
    config.LLM_CACHE.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(config.LLM_CACHE)
    db.execute("CREATE TABLE IF NOT EXISTS responses (key TEXT PRIMARY KEY, model TEXT, response TEXT)")
    return db


def _wait_for_rate_limit():
    global _last_request
    gap = 60 / config.REQUESTS_PER_MINUTE
    wait = _last_request + gap - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last_request = time.monotonic()


def _retry_delay(error):
    """Seconds the API asked us to wait, if it said; otherwise None."""
    match = re.search(r"retry in ([\d.]+)s|'retryDelay': '(\d+)s'", str(error))
    if match:
        return float(match.group(1) or match.group(2)) + 1
    return None


def generate(model, prompt, system=None, schema=None):
    """
    One deterministic (temperature 0) call. Returns text, or a parsed dict when a
    Pydantic `schema` is given. Identical requests are answered from the cache.
    """
    key = hashlib.sha256(json.dumps(
        [model, system, prompt, schema.__name__ if schema else None,
         json.dumps(schema.model_json_schema(), sort_keys=True) if schema else None]
    ).encode()).hexdigest()

    with _cache() as db:
        row = db.execute("SELECT response FROM responses WHERE key = ?", (key,)).fetchone()
    if row:
        return json.loads(row[0]) if schema else row[0]

    generation_config = types.GenerateContentConfig(
        temperature=0,
        system_instruction=system,
        response_mime_type="application/json" if schema else None,
        response_schema=schema,
    )

    for attempt in range(6):
        _wait_for_rate_limit()
        try:
            response = client().models.generate_content(model=model, contents=prompt, config=generation_config)
            break
        except errors.APIError as e:
            if e.code == 429 and "PerDay" in str(e):
                raise DailyQuota(f"Daily free-tier quota for {model} is used up. Rerun tomorrow; "
                                 "everything finished so far is cached.") from e
            if e.code not in (429, 500, 503) or attempt == 5:
                raise
            delay = _retry_delay(e) or 2 ** attempt * 5
            print(f"  {model}: HTTP {e.code}, retrying in {delay:.0f}s")
            time.sleep(delay)

    feedback = response.prompt_feedback
    if feedback and feedback.block_reason:
        raise Blocked(feedback.block_reason.value)

    text = response.text
    if not text:
        # Not cached, so a rerun tries again
        reason = response.candidates[0].finish_reason if response.candidates else "no candidates"
        raise RuntimeError(f"{model} returned no text ({reason})")
    if schema:
        # Validate before caching, so a malformed answer is never stored
        text = schema.model_validate_json(text).model_dump_json()

    with _cache() as db:
        db.execute("INSERT OR REPLACE INTO responses VALUES (?, ?, ?)", (key, model, text))
    return json.loads(text) if schema else text


def list_models():
    """Models this key can call for text generation."""
    return sorted(m.name.removeprefix("models/") for m in client().models.list()
                  if "generateContent" in (m.supported_actions or []))
