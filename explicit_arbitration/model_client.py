from __future__ import annotations

import json
import os
import ssl
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import certifi


@dataclass(slots=True)
class LiveModelConfig:
    model: str
    api_key: str
    base_url: str = "https://api.openai.com/v1"
    timeout_s: float = 60.0
    max_tokens: int = 300
    temperature: float = 0.0
    api_key_source: str = "OPENAI_API_KEY"


def _resolve_api_key() -> tuple[str, str]:
    candidates = (
        "ARBITRATION_API_KEY",
        "DEEPSEEK_API_KEY",
        "OPENAI_API_KEY",
    )
    for name in candidates:
        value = os.getenv(name, "").strip()
        if value:
            return value, name
    raise ValueError(
        "A live model API key is required. Set ARBITRATION_API_KEY, "
        "DEEPSEEK_API_KEY, or OPENAI_API_KEY."
    )


def _default_base_url(api_key_source: str) -> str:
    configured = (
        os.getenv("ARBITRATION_BASE_URL", "").strip()
        or os.getenv("OPENAI_BASE_URL", "").strip()
    )
    if configured:
        return configured
    if api_key_source == "DEEPSEEK_API_KEY":
        return "https://api.deepseek.com"
    return "https://api.openai.com/v1"


def _default_model(base_url: str) -> str:
    configured = os.getenv("MODEL_NAME", "").strip()
    if configured:
        return configured
    if "deepseek.com" in base_url:
        return "deepseek-v4-flash"
    return "gpt-4.1-mini"


def load_live_model_config(
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> LiveModelConfig:
    api_key, api_key_source = _resolve_api_key()
    base_url = _default_base_url(api_key_source)
    timeout_s = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "60").strip() or "60")
    resolved_model = model or _default_model(base_url)
    resolved_max_tokens = int(
        max_tokens if max_tokens is not None else os.getenv("MAX_TOKENS", "300")
    )
    resolved_temperature = float(
        temperature
        if temperature is not None
        else os.getenv("TEMPERATURE", "0")
    )

    return LiveModelConfig(
        model=resolved_model,
        api_key=api_key,
        base_url=base_url,
        timeout_s=timeout_s,
        max_tokens=resolved_max_tokens,
        temperature=resolved_temperature,
        api_key_source=api_key_source,
    )


def _extract_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("model response missing choices")

    first = choices[0]
    if not isinstance(first, dict):
        raise ValueError("model response choice must be an object")

    message = first.get("message")
    if not isinstance(message, dict):
        raise ValueError("model response missing message")

    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text")
                if isinstance(text, str):
                    text_parts.append(text)
        if text_parts:
            return "".join(text_parts)
    raise ValueError("model response content is not text")


def call_openai_compatible(prompt: str, config: LiveModelConfig) -> str:
    endpoint = f"{config.base_url.rstrip('/')}/chat/completions"
    body = {
        "model": config.model,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You must return strict JSON only. "
                    "No markdown, no prose outside JSON."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    }
    data = json.dumps(body).encode("utf-8")

    request = Request(
        endpoint,
        data=data,
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    ssl_context = ssl.create_default_context(cafile=certifi.where())

    try:
        with urlopen(
            request,
            timeout=config.timeout_s,
            context=ssl_context,
        ) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"model HTTP error {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"model network error: {exc.reason}") from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"model returned non-JSON API payload: {raw}") from exc

    return _extract_text(payload)
