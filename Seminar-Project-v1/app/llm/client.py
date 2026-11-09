"""KKU IntelSphere OpenAI-compatible chat client; no database rows are sent."""
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
from time import perf_counter
import urllib.error
import urllib.parse
import urllib.request

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent.parent


class LLMConfigurationError(ValueError):
    pass


class LLMCallError(RuntimeError):
    pass


@dataclass
class Settings:
    provider: str
    base_url: str
    model: str
    api_key: str = field(repr=False)
    temperature: float = 0
    max_output_tokens: int = 2048
    timeout_seconds: float = 45


def load_settings(*, require_key: bool = True) -> Settings:
    # Re-read the local ignored file each call; saving a key needs no restart.
    local = dotenv_values(ROOT / ".env.llm")

    def setting(key, default=""):
        return os.environ.get(key) or local.get(key) or default

    s = Settings(provider=setting("LLM_PROVIDER", "kku-intelsphere"),
                 base_url=setting("LLM_BASE_URL", "https://gen.ai.kku.ac.th/api/v1").rstrip("/"),
                 model=setting("LLM_MODEL", "gpt-5.6-luna"),
                 api_key=setting("LLM_API_KEY"))
    parsed = urllib.parse.urlsplit(s.base_url)
    if (s.provider != "kku-intelsphere" or parsed.scheme != "https"
            or parsed.hostname != "gen.ai.kku.ac.th" or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.port not in (None, 443)
            or parsed.path.rstrip("/") != "/api/v1"):
        raise LLMConfigurationError("Use the IntelSphere base URL shown in API Platform")
    try:
        s.temperature = float(setting("LLM_TEMPERATURE", "0"))
        s.max_output_tokens = int(setting("LLM_MAX_OUTPUT_TOKENS", "2048"))
        s.timeout_seconds = float(setting("LLM_TIMEOUT_SECONDS", "45"))
    except ValueError as exc:
        raise LLMConfigurationError("Invalid numeric LLM setting") from exc
    if not s.model or not 0 <= s.temperature <= 2 or not 256 <= s.max_output_tokens <= 8192 or not 1 <= s.timeout_seconds <= 60:
        raise LLMConfigurationError("LLM settings exceed demo limits")
    if require_key and not s.api_key.strip():
        raise LLMConfigurationError("Paste your IntelSphere API key into .env.llm (LLM_API_KEY), then save")
    return s


def configuration_status() -> dict:
    try:
        s = load_settings(require_key=False)
    except LLMConfigurationError as exc:
        return {"configured": False, "message": str(exc)}
    return {"configured": bool(s.api_key.strip()), "provider": s.provider,
            "base_url": s.base_url, "requested_model": s.model,
            "temperature": s.temperature, "max_output_tokens": s.max_output_tokens,
            "timeout_seconds": s.timeout_seconds}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # never forward the Authorization header to a redirect


def _post_json(url: str, payload: dict, settings: Settings) -> dict:
    request = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + settings.api_key}, method="POST")
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=settings.timeout_seconds) as response:
            body = response.read(2_000_001)
        if len(body) > 2_000_000:
            raise LLMCallError("Provider response exceeds size limit")
        return json.loads(body)
    except urllib.error.HTTPError as exc:
        # Decode known provider error codes without echoing arbitrary bodies.
        try:
            error = json.loads(exc.read(4096)).get("error")
        except (ValueError, AttributeError):
            error = None
        if error == "Invalid model":
            raise LLMCallError("IntelSphere: Invalid model; select an ID from API Platform / Models") from None
        raise LLMCallError(f"IntelSphere HTTP {exc.code}; check key, model and quota in API Platform") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise LLMCallError("IntelSphere network error or request timeout") from None
    except (ValueError, UnicodeError):
        raise LLMCallError("IntelSphere returned an invalid JSON response") from None


def generate(bundle: dict) -> dict:
    s = load_settings()
    payload = {"model": s.model, "messages": bundle["messages"], "stream": False,
               "temperature": s.temperature, "max_tokens": s.max_output_tokens}
    start = perf_counter()
    response = _post_json(s.base_url + "/chat/completions", payload, s)
    elapsed = round((perf_counter() - start) * 1000, 3)
    try:
        choice = response["choices"][0]
        if choice.get("finish_reason") == "length":
            raise LLMCallError("Model output was truncated; SQL was not executed")
        content = choice["message"]["content"]
        if not isinstance(content, str):
            raise TypeError
        usage = response.get("usage") or {}
    except (KeyError, IndexError, TypeError):
        raise LLMCallError("IntelSphere response does not match chat/completions format") from None
    def tokens(name):
        v = usage.get(name)
        return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else None
    return {"content": content, "provider": s.provider, "requested_model": s.model,
            "returned_model": response.get("model"), "response_id": response.get("id"),
            "finish_reason": choice.get("finish_reason"), "temperature": s.temperature,
            "max_output_tokens": s.max_output_tokens, "generation_ms": elapsed,
            "input_tokens": tokens("prompt_tokens"), "output_tokens": tokens("completion_tokens"),
            "total_tokens": tokens("total_tokens"), "retries": 0,
            "cost": None, "cost_note": "IntelSphere billing/quota rates have not been configured; tokens are not a billed currency amount"}
