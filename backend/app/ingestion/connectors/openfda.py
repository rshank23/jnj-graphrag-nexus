"""openFDA connectors: drug labels, FAERS adverse events (+ PRR/ROR), enforcement recalls, GUDID device UDI and MAUDE.

openFDA returns HTTP 404 when a search matches nothing; that is mapped to an empty result, not an error.
"""
from __future__ import annotations

import asyncio
import re
from typing import Any, Dict, List, Optional

import httpx

from app.config import get_settings
from app.ingestion.connectors.base import SourceConnector, lucene_phrase
from app.ingestion.connectors.signals import contingency_from_totals, disproportionality

OPENFDA = "https://api.fda.gov"
LABEL_SECTIONS = {
    "boxed_warning": "boxed_warning",
    "indications_and_usage": "indications",
    "contraindications": "contraindications",
    "warnings_and_cautions": "warnings",
    "warnings": "warnings",
    "adverse_reactions": "adverse_reactions",
    "dosage_and_administration": "dosage",
    "drug_interactions": "drug_interactions",
    "mechanism_of_action": "mechanism",
    "clinical_studies": "clinical_studies",
}
JNJ_DEVICE_COMPANIES = ("Biosense Webster", "DePuy", "Ethicon", "Shockwave", "Johnson & Johnson", "Abiomed", "Cerenovus",
                        "Mentor", "Auris", "Synthes", "Codman", "Acclarent")


def _first(v: Any) -> str:
    if isinstance(v, list):
        return str(v[0]) if v else ""
    return str(v or "")


def _clean(text: str, limit: int = 4000) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


class OpenFDAConnector(SourceConnector):
    base_url = OPENFDA
    endpoint = ""

    async def search(self, search: str, limit: int = 5, count: Optional[str] = None, skip: int = 0) -> Dict[str, Any]:
        params: Dict[str, Any] = {"search": search, "limit": min(limit, 1000)}
        if count:
            params = {"search": search, "count": count, "limit": min(limit, 1000)} if search else {"count": count, "limit": limit}
        elif skip:
            params["skip"] = min(skip, 25_000)  # openFDA hard ceiling for skip paging
        key = get_settings().openfda_api_key
        if key:
            params["api_key"] = key
        try:
            payload = await self.get_json(self.endpoint, params=params)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return {"meta": {"results": {"total": 0}}, "results": []}
            raise
        if not isinstance(payload, dict):  # HTML or other unexpected 200 body
            return {"meta": {"results": {"total": 0}}, "results": []}
        return payload

    async def total(self, search: str = "") -> int:
        params: Dict[str, Any] = {"limit": 1}
        if search:
            params["search"] = search
        key = get_settings().openfda_api_key
        if key:
            params["api_key"] = key
        try:
            payload = await self.get_json(self.endpoint, params=params)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return 0
            raise
        return int(payload.get("meta", {}).get("results", {}).get("total", 0))


class DrugLabelConnector(OpenFDAConnector):
    source = "openfda_drug_label"
    cadence = "weekly"
    endpoint = "/drug/label.json"

    async def fetch(self, brand: str) -> Optional[Dict[str, Any]]:
        brand = self.guard(brand)
        payload = await self.search(f"openfda.brand_name:{lucene_phrase(brand)}", limit=1)
        results = payload.get("results") or []
        if not results:
            payload = await self.search(f"openfda.generic_name:{lucene_phrase(brand)}", limit=1)
            results = payload.get("results") or []
        return self.normalize(results[0]) if results else None

    @staticmethod
    def normalize(raw: Dict[str, Any]) -> Dict[str, Any]:
        of = raw.get("openfda", {})
        sections = {}
        for field, name in LABEL_SECTIONS.items():
            if raw.get(field) and name not in sections:
                sections[name] = _clean(_first(raw[field]))
        return {
            "set_id": raw.get("set_id") or _first(of.get("spl_set_id")),
            "version": str(raw.get("version") or ""),
            "effective_time": raw.get("effective_time"),
            "brand_name": _first(of.get("brand_name")),
            "generic_name": _first(of.get("generic_name")),
            "manufacturer": _first(of.get("manufacturer_name")),
            "rxcui": of.get("rxcui", []),
            "sections": sections,
        }


class DrugEventConnector(OpenFDAConnector):
    """FAERS: top reactions for a drug plus disproportionality against the full database."""

    source = "openfda_faers"
    cadence = "weekly"
    endpoint = "/drug/event.json"

    async def fetch_signals(self, brand: str, top_n: int = 5) -> Dict[str, Any]:
        brand = self.guard(brand)
        # Newer products are often missing from the harmonised openfda.* fields, so query the reported product name first.
        top: Dict[str, Any] = {}
        drug_q = ""
        for field in ("patient.drug.medicinalproduct", "patient.drug.openfda.brand_name"):
            drug_q = f"{field}:{lucene_phrase(brand)}"
            top = await self.search(drug_q, count="patient.reaction.reactionmeddrapt.exact", limit=top_n)
            if top.get("results"):
                break
        reactions = [(r["term"], int(r["count"])) for r in (top.get("results") or [])[:top_n]]
        if not reactions:
            return {"brand": brand, "drug_total": 0, "all_total": 0, "signals": []}
        drug_total, all_total = await asyncio.gather(self.total(drug_q), self.total(""))
        reaction_totals = await asyncio.gather(*(self.total(f"patient.reaction.reactionmeddrapt.exact:{lucene_phrase(t)}")
                                                 for t, _ in reactions))
        signals = []
        for (term, a), r_total in zip(reactions, reaction_totals):
            stats = disproportionality(*contingency_from_totals(a, drug_total, r_total, all_total))
            signals.append({"reaction": term.title(), "reports": a, **stats.to_dict()})
        return {"brand": brand, "drug_total": drug_total, "all_total": all_total, "signals": signals}


class EnforcementConnector(OpenFDAConnector):
    source = "openfda_enforcement"
    cadence = "weekly"

    def __init__(self, kind: str = "drug", client: Optional[httpx.AsyncClient] = None):
        super().__init__(client)
        self.kind = kind
        self.endpoint = f"/{kind}/enforcement.json"
        self.source = f"openfda_{kind}_enforcement"

    async def fetch(self, term: str, limit: int = 5, jnj_only: bool = True) -> List[Dict[str, Any]]:
        term = self.guard(term)
        payload = await self.search(f"product_description:{lucene_phrase(term)}", limit=limit * 4 if jnj_only else limit)
        firms = JNJ_DEVICE_COMPANIES + ("Janssen", "Actelion", "Patriot Pharmaceuticals", "Intra-Cellular")
        out = []
        for r in payload.get("results") or []:
            firm = r.get("recalling_firm") or ""
            # Third-party kits that merely contain a J&J component are not J&J recalls.
            if jnj_only and not any(f.lower() in firm.lower() for f in firms):
                continue
            out.append({
                "recall_number": r.get("recall_number"),
                "classification": r.get("classification"),
                "status": r.get("status"),
                "reason": _clean(r.get("reason_for_recall", ""), 600),
                "product_description": _clean(r.get("product_description", ""), 400),
                "recalling_firm": firm,
                "report_date": r.get("report_date"),
            })
        return out[:limit]


class DeviceUDIConnector(OpenFDAConnector):
    """AccessGUDID via openFDA device/udi: the sanctioned replacement for scraping jnjmedtech.com."""

    source = "openfda_gudid"
    cadence = "monthly"
    endpoint = "/device/udi.json"

    async def fetch(self, brand: str, limit: int = 10, jnj_only: bool = True) -> List[Dict[str, Any]]:
        brand = self.guard(brand)
        payload = await self.search(f"brand_name:{lucene_phrase(brand)}", limit=limit)
        out: Dict[str, Dict[str, Any]] = {}
        for r in payload.get("results") or []:
            company = r.get("company_name") or ""
            if jnj_only and not any(c.lower() in company.lower() for c in JNJ_DEVICE_COMPANIES):
                continue
            key = (r.get("brand_name") or "").upper()
            if key in out:
                out[key]["models"].append(r.get("version_or_model_number"))
                continue
            gmdn = r.get("gmdn_terms") or []
            di = next((i.get("id") for i in r.get("identifiers") or [] if i.get("type") == "Primary"), None)
            out[key] = {
                "brand_name": r.get("brand_name"),
                "company_name": company,
                "description": _clean(r.get("device_description") or "", 500),
                "gmdn_term": gmdn[0].get("name") if gmdn else None,
                "gmdn_definition": _clean(gmdn[0].get("definition", ""), 400) if gmdn else None,
                "primary_di": di,
                "product_codes": [p.get("code") for p in r.get("product_codes") or []],
                "models": [r.get("version_or_model_number")],
                "is_rx": r.get("is_rx"),
            }
        return list(out.values())


class DeviceEventConnector(OpenFDAConnector):
    """MAUDE adverse-event report counts by event type for a device brand."""

    source = "openfda_maude"
    cadence = "weekly"
    endpoint = "/device/event.json"

    async def fetch_counts(self, brand: str) -> Dict[str, int]:
        brand = self.guard(brand)
        payload = await self.search(f"device.brand_name:{lucene_phrase(brand)}", count="event_type.exact", limit=10)
        return {r["term"]: int(r["count"]) for r in payload.get("results") or []}
