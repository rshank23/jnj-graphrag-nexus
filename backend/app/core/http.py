"""Resilient HTTP: retry on 429/5xx honouring Retry-After, TTL caching and secret redaction for logs."""
from __future__ import annotations

import asyncio
import email.utils
import logging
import re
import threading
import time
from typing import Any, Callable, Dict, Hashable, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

RETRY_STATUSES = {429, 500, 502, 503, 504}
DEFAULT_DELAYS: Tuple[float, ...] = (2.0, 5.0, 10.0)
MAX_RETRY_AFTER = 60.0
USER_AGENT = "Mozilla/5.0 (compatible; JnJ-GraphRAG-Nexus/1.0; +https://www.jnj.com)"
_SECRET_PARAM_RE = re.compile(r"(?i)((?:api_?key|token|key|secret|password)=)[^&\s]+")


def redact_url(url: str) -> str:
    """Strip credentials from query strings before they reach logs or error messages."""
    return _SECRET_PARAM_RE.sub(r"\1***", str(url))


def parse_retry_after(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return min(float(value), MAX_RETRY_AFTER)
    try:
        dt = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(dt.timestamp() - time.time(), MAX_RETRY_AFTER))


def http_verify() -> Any:
    """Prefer the OS trust store (corporate TLS-inspection roots) when `truststore` is installed; else certifi."""
    try:
        import ssl

        import truststore

        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except Exception:
        return True


class TTLCache:
    """Thread-safe in-process cache with per-entry expiry and a size bound."""

    def __init__(self, ttl_seconds: float = 3600.0, max_entries: int = 512):
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        self._data: Dict[Hashable, Tuple[float, Any]] = {}
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: Hashable) -> Any:
        with self._lock:
            item = self._data.get(key)
            if item is None or item[0] < time.monotonic():
                self._data.pop(key, None)
                self.misses += 1
                return None
            self.hits += 1
            return item[1]

    def set(self, key: Hashable, value: Any, ttl: Optional[float] = None) -> None:
        with self._lock:
            if key not in self._data and len(self._data) >= self.max_entries:
                oldest = min(self._data, key=lambda k: self._data[k][0])
                self._data.pop(oldest, None)
            self._data[key] = (time.monotonic() + (ttl if ttl is not None else self.ttl), value)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def stats(self) -> Dict[str, int]:
        return {"entries": len(self._data), "hits": self.hits, "misses": self.misses}


response_cache = TTLCache(ttl_seconds=6 * 3600)


async def get_with_retry(url: str, params: Optional[Dict[str, Any]] = None, client: Optional[httpx.AsyncClient] = None,
                         timeout: float = 15.0, delays: Tuple[float, ...] = DEFAULT_DELAYS,
                         sleep: Callable[[float], Any] = asyncio.sleep, headers: Optional[Dict[str, str]] = None) -> httpx.Response:
    """GET with bounded retries on transient failures. Non-retryable 4xx raise immediately."""
    attempts = len(delays) + 1
    last_exc: Optional[Exception] = None
    own = client is None
    if own:
        client = httpx.AsyncClient(timeout=timeout, follow_redirects=True, verify=http_verify(),
                                   headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US", **(headers or {})})
    try:
        for attempt in range(attempts):
            try:
                resp = await client.get(url, params=params)
            except httpx.TransportError as exc:
                last_exc = exc
                if attempt >= attempts - 1:
                    break
                logger.warning("Transport error for %s (%s); retry %d/%d", redact_url(url), type(exc).__name__, attempt + 1, attempts - 1)
                await sleep(delays[attempt])
                continue
            if resp.status_code in RETRY_STATUSES and attempt < attempts - 1:
                wait = parse_retry_after(resp.headers.get("Retry-After"))
                wait = delays[attempt] if wait is None else wait
                logger.warning("HTTP %s from %s; retry %d/%d in %.1fs", resp.status_code, redact_url(str(resp.url)),
                               attempt + 1, attempts - 1, wait)
                await sleep(wait)
                continue
            resp.raise_for_status()
            return resp
        raise last_exc or httpx.HTTPError(f"Exhausted retries for {redact_url(url)}")
    finally:
        if own:
            await client.aclose()


async def get_json_cached(url: str, params: Optional[Dict[str, Any]] = None, client: Optional[httpx.AsyncClient] = None,
                          ttl: Optional[float] = None, **kwargs: Any) -> Any:
    key = (url, tuple(sorted((params or {}).items())))
    cached = response_cache.get(key)
    if cached is not None:
        return cached
    resp = await get_with_retry(url, params=params, client=client, **kwargs)
    payload = resp.json()
    response_cache.set(key, payload, ttl)
    return payload
