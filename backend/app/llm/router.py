"""ModelRouter: Azure OpenAI -> OpenAI -> Gemini fallback with YAML-versioned prompts and per-call cost tracking.

Returns ``None`` when no provider is configured or all fail, so callers always keep the deterministic grounded answer.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx
import yaml

from app.config import get_settings

logger = logging.getLogger(__name__)

PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"

# USD per 1M tokens (input, output). Update from the Azure price sheet for the negotiated rate.
PRICING: Dict[str, Tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gemini-1.5-flash": (0.075, 0.30),
}


@dataclass(frozen=True)
class Prompt:
    name: str
    version: str
    system: str
    template: str

    def render(self, **variables: Any) -> str:
        return self.template.format(**variables)


@lru_cache(maxsize=32)
def load_prompt(name: str) -> Prompt:
    data = yaml.safe_load((PROMPT_DIR / f"{name}.yaml").read_text(encoding="utf-8"))
    return Prompt(name=data["name"], version=str(data["version"]), system=data["system"].strip(), template=data["template"])


def list_prompts() -> List[Dict[str, str]]:
    return [{"name": p.name, "version": p.version} for p in (load_prompt(f.stem) for f in sorted(PROMPT_DIR.glob("*.yaml")))]


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    pin, pout = PRICING.get(model, PRICING["gpt-4o-mini"])
    return round((prompt_tokens * pin + completion_tokens * pout) / 1_000_000, 6)


@dataclass
class Completion:
    text: str
    provider: str
    model: str
    prompt_version: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    latency_ms: float


ProviderFn = Callable[[str, str, float], Tuple[str, int, int]]


class ModelRouter:
    def __init__(self, providers: Optional[List[Tuple[str, str, ProviderFn]]] = None):
        self._providers = providers

    def providers(self) -> List[Tuple[str, str, ProviderFn]]:
        if self._providers is not None:
            return self._providers
        s = get_settings()
        out: List[Tuple[str, str, ProviderFn]] = []
        if s.azure_openai_endpoint and s.azure_openai_api_key:
            out.append(("azure-openai", s.azure_openai_deployment, self._azure_openai))
        if s.openai_api_key:
            out.append(("openai", s.openai_model, self._openai))
        if s.gemini_api_key:
            out.append(("gemini", s.gemini_model, self._gemini))
        return out

    def complete(self, prompt_name: str, temperature: float = 0.1, **variables: Any) -> Optional[Completion]:
        prompt = load_prompt(prompt_name)
        user = prompt.render(**variables)
        for provider, model, fn in self.providers():
            t0 = time.perf_counter()
            try:
                text, ptoks, ctoks = fn(prompt.system, user, temperature)
            except Exception as exc:
                logger.warning("LLM provider %s failed (%s); trying next", provider, type(exc).__name__)
                _log_usage(provider, model, prompt.version, 0, 0, 0.0, False)
                continue
            ptoks = ptoks or (len(prompt.system) + len(user)) // 4
            ctoks = ctoks or len(text) // 4
            cost = estimate_cost(model, ptoks, ctoks)
            _log_usage(provider, model, f"{prompt.name}@{prompt.version}", ptoks, ctoks, cost, True)
            return Completion(text=text, provider=provider, model=model, prompt_version=f"{prompt.name}@{prompt.version}",
                              prompt_tokens=ptoks, completion_tokens=ctoks, cost_usd=cost,
                              latency_ms=round((time.perf_counter() - t0) * 1000, 1))
        return None

    # ------------------------------------------------------------------ providers
    @staticmethod
    def _chat_payload(system: str, user: str, temperature: float) -> Dict[str, Any]:
        return {"temperature": temperature, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}

    def _azure_openai(self, system: str, user: str, temperature: float) -> Tuple[str, int, int]:
        s = get_settings()
        url = f"{s.azure_openai_endpoint.rstrip('/')}/openai/deployments/{s.azure_openai_deployment}/chat/completions"
        r = httpx.post(url, params={"api-version": s.azure_openai_api_version}, headers={"api-key": s.azure_openai_api_key},
                       json=self._chat_payload(system, user, temperature), timeout=45)
        r.raise_for_status()
        data = r.json()
        u = data.get("usage", {})
        return data["choices"][0]["message"]["content"], u.get("prompt_tokens", 0), u.get("completion_tokens", 0)

    def _openai(self, system: str, user: str, temperature: float) -> Tuple[str, int, int]:
        s = get_settings()
        r = httpx.post("https://api.openai.com/v1/chat/completions", headers={"Authorization": f"Bearer {s.openai_api_key}"},
                       json={"model": s.openai_model, **self._chat_payload(system, user, temperature)}, timeout=45)
        r.raise_for_status()
        data = r.json()
        u = data.get("usage", {})
        return data["choices"][0]["message"]["content"], u.get("prompt_tokens", 0), u.get("completion_tokens", 0)

    def _gemini(self, system: str, user: str, temperature: float) -> Tuple[str, int, int]:
        s = get_settings()
        r = httpx.post(f"https://generativelanguage.googleapis.com/v1beta/models/{s.gemini_model}:generateContent",
                       headers={"x-goog-api-key": s.gemini_api_key}, timeout=45,
                       json={"systemInstruction": {"parts": [{"text": system}]}, "contents": [{"parts": [{"text": user}]}],
                             "generationConfig": {"temperature": temperature}})
        r.raise_for_status()
        data = r.json()
        u = data.get("usageMetadata", {})
        return data["candidates"][0]["content"]["parts"][0]["text"], u.get("promptTokenCount", 0), u.get("candidatesTokenCount", 0)


def _log_usage(provider: str, model: str, version: str, ptoks: int, ctoks: int, cost: float, ok: bool) -> None:
    try:
        from app.core.db import get_db

        get_db().log_llm_usage(provider, model, version, ptoks, ctoks, cost, ok)
    except Exception:  # pragma: no cover - metering must never break generation
        logger.debug("LLM usage logging failed", exc_info=True)


_router: Optional[ModelRouter] = None


def get_router() -> ModelRouter:
    global _router
    if _router is None:
        _router = ModelRouter()
    return _router


def set_router(router: Optional[ModelRouter]) -> None:
    global _router
    _router = router
