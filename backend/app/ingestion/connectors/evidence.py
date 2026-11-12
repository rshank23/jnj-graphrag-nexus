"""Evidence connectors: ClinicalTrials.gov v2, PubMed E-utilities and NLM RxNorm."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.config import get_settings
from app.ingestion.connectors.base import SourceConnector


class ClinicalTrialsConnector(SourceConnector):
    source = "clinicaltrials_gov"
    cadence = "weekly"
    base_url = "https://clinicaltrials.gov/api/v2"

    async def fetch(self, intervention: str, limit: int = 5) -> List[Dict[str, Any]]:
        intervention = self.guard(intervention)
        payload = await self.get_json("/studies", params={"query.intr": intervention, "pageSize": limit, "sort": "LastUpdatePostDate:desc"})
        return [self.normalize(s) for s in (payload.get("studies") or [])[:limit]]

    @staticmethod
    def normalize(study: Dict[str, Any]) -> Dict[str, Any]:
        p = study.get("protocolSection", {})
        ident = p.get("identificationModule", {})
        status = p.get("statusModule", {})
        design = p.get("designModule", {})
        sponsor = p.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {})
        nct = ident.get("nctId")
        return {
            "nct_id": nct,
            "title": ident.get("briefTitle") or ident.get("officialTitle") or nct,
            "status": status.get("overallStatus"),
            "phases": design.get("phases") or [],
            "conditions": p.get("conditionsModule", {}).get("conditions", [])[:6],
            "sponsor": sponsor.get("name"),
            "start_date": (status.get("startDateStruct") or {}).get("date"),
            "last_update": (status.get("lastUpdatePostDateStruct") or {}).get("date"),
            "enrollment": (design.get("enrollmentInfo") or {}).get("count"),
            "url": f"https://clinicaltrials.gov/study/{nct}" if nct else None,
        }


class PubMedConnector(SourceConnector):
    source = "pubmed"
    cadence = "weekly"
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def _params(self, **kw: Any) -> Dict[str, Any]:
        key = get_settings().ncbi_api_key
        return {**kw, "retmode": "json", **({"api_key": key} if key else {})}

    async def fetch(self, term: str, limit: int = 5) -> List[Dict[str, Any]]:
        term = self.guard(term)
        search = await self.get_json("/esearch.fcgi", params=self._params(db="pubmed", term=term, retmax=limit, sort="relevance"))
        ids = (search.get("esearchresult") or {}).get("idlist") or []
        if not ids:
            return []
        summary = await self.get_json("/esummary.fcgi", params=self._params(db="pubmed", id=",".join(ids)))
        result = summary.get("result") or {}
        out = []
        for pmid in ids:
            r = result.get(pmid) or {}
            authors = [a.get("name") for a in r.get("authors") or []][:3]
            out.append({
                "pmid": pmid,
                "title": r.get("title") or f"PMID {pmid}",
                "journal": r.get("fulljournalname") or r.get("source"),
                "pubdate": r.get("pubdate"),
                "year": int(str(r.get("pubdate", ""))[:4]) if str(r.get("pubdate", ""))[:4].isdigit() else None,
                "authors": authors,
                "pubtypes": r.get("pubtype") or [],
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            })
        return out


class RxNormConnector(SourceConnector):
    """Brand / generic / misspelled drug name -> RxCUI with canonical name (NLM RxNav)."""

    source = "rxnorm"
    cadence = "monthly"
    base_url = "https://rxnav.nlm.nih.gov/REST"

    async def resolve(self, name: str) -> Optional[Dict[str, Any]]:
        name = self.guard(name)
        exact = await self.get_json("/rxcui.json", params={"name": name, "search": 2})
        ids = ((exact.get("idGroup") or {}).get("rxnormId")) or []
        method = "exact"
        if not ids:
            approx = await self.get_json("/approximateTerm.json", params={"term": name, "maxEntries": 3})
            cands = ((approx.get("approximateGroup") or {}).get("candidate")) or []
            ids = [c["rxcui"] for c in cands if c.get("rxcui")]
            method = "approximate"
        if not ids:
            sugg = await self.get_json("/spellingsuggestions.json", params={"name": name})
            options = (((sugg.get("suggestionGroup") or {}).get("suggestionList") or {}).get("suggestion")) or []
            return {"query": name, "rxcui": None, "method": "spelling", "suggestions": options[:5]} if options else None
        props = await self.get_json(f"/rxcui/{ids[0]}/properties.json")
        p = props.get("properties") or {}
        return {"query": name, "rxcui": ids[0], "name": p.get("name"), "tty": p.get("tty"), "method": method}
