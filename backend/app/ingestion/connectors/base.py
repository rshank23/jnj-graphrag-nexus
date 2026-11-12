"""Connector protocol shared by all sanctioned public data sources."""
from __future__ import annotations

import re
from typing import Any, Dict, Optional

import httpx

from app.config import get_settings
from app.core.http import get_json_cached, get_with_retry
from app.graph.seed_data import is_kenvue_brand


class KenvueQueryRejected(ValueError):
    pass


class SourceConnector:
    """Base class: one instance per public source with its own refresh cadence and injectable HTTP client."""

    source: str = "base"
    cadence: str = "weekly"
    base_url: str = ""

    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        self.client = client
        self.timeout = get_settings().http_timeout_seconds

    @staticmethod
    def guard(term: str) -> str:
        term = (term or "").strip()
        if not term:
            raise ValueError("A search term is required")
        if is_kenvue_brand(term):
            raise KenvueQueryRejected(f"'{term}' is a Kenvue consumer-health brand (outside the J&J portfolio)")
        return term

    async def get_json(self, path_or_url: str, params: Optional[Dict[str, Any]] = None, cache: bool = True) -> Any:
        url = path_or_url if path_or_url.startswith("http") else f"{self.base_url}{path_or_url}"
        if cache:
            return await get_json_cached(url, params=params, client=self.client, timeout=self.timeout)
        return (await get_with_retry(url, params=params, client=self.client, timeout=self.timeout)).json()


def lucene_phrase(term: str) -> str:
    """Quote a term for openFDA / Lucene search, stripping characters that would break the query."""
    return '"' + re.sub(r'["\\:()\[\]{}^~*?+!]', " ", term).strip() + '"'
