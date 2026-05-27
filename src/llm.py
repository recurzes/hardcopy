from __future__ import annotations

from src.config import LLM_API_KEY, LLM_MODEL, LLM_PROVIDER, OLLAMA_HOST

DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-sonnet-4-20250514",
    "ollama": "llama3.2",
}


class LLMError(Exception):
    """Raised when LLM configuration or completion fails."""


def llm_complete(system_prompt: str, user_prompt: str, *, timeout: float = 120.0) -> str:
    """Send a completion request to the configured LLM provider."""
    provider = (LLM_PROVIDER or "openai").lower()

    if provider == "openai":
        return _openai_complete(system_prompt, user_prompt, timeout=timeout)
    if provider == "anthropic":
        return _anthropic_complete(system_prompt, user_prompt, timeout=timeout)
    if provider == "ollama":
        return _ollama_complete(system_prompt, user_prompt, timeout=timeout)

    raise LLMError(f"Unknown LLM_PROVIDER: {provider!r}. Use openai, anthropic, or ollama.")


def _resolve_model(provider: str) -> str:
    if LLM_MODEL:
        return LLM_MODEL
    return DEFAULT_MODELS[provider]


def _openai_complete(system_prompt: str, user_prompt: str, *, timeout: float) -> str:
    if not LLM_API_KEY:
        raise LLMError("LLM_API_KEY not set (required for openai)")

    try:
        from openai import OpenAI
    except ImportError as e:
        raise LLMError("openai package not installed. Run: pip install openai") from e

    client = OpenAI(api_key=LLM_API_KEY, timeout=timeout)
    response = client.chat.completions.create(
        model=_resolve_model("openai"),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
    )
    content = response.choices[0].message.content
    if not content:
        raise LLMError("OpenAI returned an empty response")
    return content


def _anthropic_complete(system_prompt: str, user_prompt: str, *, timeout: float) -> str:
    if not LLM_API_KEY:
        raise LLMError("LLM_API_KEY not set (required for anthropic)")

    try:
        from anthropic import Anthropic
    except ImportError as e:
        raise LLMError(
            "anthropic package not installed. Run: pip install anthropic"
        ) from e

    client = Anthropic(api_key=LLM_API_KEY, timeout=timeout)
    response = client.messages.create(
        model=_resolve_model("anthropic"),
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
        temperature=0.3,
    )
    text_parts = [block.text for block in response.content if block.type == "text"]
    if not text_parts:
        raise LLMError("Anthropic returned an empty response")
    return "\n".join(text_parts)


def _ollama_complete(system_prompt: str, user_prompt: str, *, timeout: float) -> str:
    import httpx

    payload = {
        "model": _resolve_model("ollama"),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": {"temperature": 0.3},
    }

    try:
        response = httpx.post(
            f"{OLLAMA_HOST.rstrip('/')}/api/chat",
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
    except httpx.HTTPError as e:
        raise LLMError(f"Ollama request failed: {e}") from e

    data = response.json()
    content = data.get("message", {}).get("content")
    if not content:
        raise LLMError("Ollama returned an empty response")
    return content
