"""Map public regulatory / evidence data into the graph, with freshness tracking, audit and two-phase expansion."""
from __future__ import annotations

import asyncio
import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx

from app.core.db import get_db
from app.graph.seed_data import IM, MT, is_kenvue_brand
from app.ingestion.connectors import (ClinicalTrialsConnector, DeviceEventConnector, DeviceUDIConnector, DrugEventConnector,
                                      DrugLabelConnector, EnforcementConnector, KenvueQueryRejected, PubMedConnector, RxNormConnector)
from app.ingestion.jnj_scraper import MEDTECH_SPECIALTIES, reconcile_with_existing, scraped_to_graph
from app.ingestion.label_monitor import affected_claims, record_label
from app.ingestion.pdf_extractor import slugify
from app.models.schemas import EdgeType, GraphEdge, GraphNode, NodeType, ScrapedProduct
from app.rag.entity_resolver import get_resolver

logger = logging.getLogger(__name__)

SyncResult = Dict[str, Any]
LABEL_PROP_MAP = {"indications": "indication", "mechanism": "mechanism", "contraindications": "contraindication"}


def _result(source: str, status: str, messages: List[str], nodes: List[GraphNode] = (), edges: List[GraphEdge] = (),
            extra: Optional[Dict[str, Any]] = None) -> SyncResult:
    return {"source": source, "status": status, "messages": messages, "added_nodes": list(nodes), "added_edges": list(edges), **(extra or {})}


def _fmt_date(yyyymmdd: Optional[str]) -> Optional[str]:
    if not yyyymmdd or len(yyyymmdd) != 8:
        return yyyymmdd
    try:
        return datetime.strptime(yyyymmdd, "%Y%m%d").strftime("%Y-%m-%d")
    except ValueError:
        return yyyymmdd


async def _tracked(source: str, cadence: str, actor: Optional[str], fn: Callable[[], Any]) -> SyncResult:
    """Run one connector sync with failure isolation, freshness bookkeeping and an audit entry."""
    db = get_db()
    try:
        res: SyncResult = await fn()
    except KenvueQueryRejected as exc:
        return _result(source, "rejected", [str(exc)])
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        db.mark_source(source, ok=False, error=f"{type(exc).__name__}: {exc}", cadence=cadence)
        return _result(source, "error", [f"{source} unavailable: {type(exc).__name__}: {exc}"])
    db.mark_source(source, ok=True, items=len(res["added_nodes"]), cadence=cadence, watermark=res.get("watermark"))
    db.audit("ingest", source, {"status": res["status"], "nodes": [n.id for n in res["added_nodes"]][:50],
                                "edges": len(res["added_edges"])}, actor)
    return res


def _product_id(store, name: str) -> Optional[str]:
    return get_resolver(store).resolve_name(name)


# --------------------------------------------------------------------------- drug label (+ label change monitoring)
async def sync_label(store, name: str, client: Optional[httpx.AsyncClient] = None, actor: Optional[str] = None) -> SyncResult:
    conn = DrugLabelConnector(client)

    async def run() -> SyncResult:
        label = await conn.fetch(name)
        if not label:
            return _result(conn.source, "not-found", [f"No openFDA drug label found for '{name}'"])
        if is_kenvue_brand(label["brand_name"]) or is_kenvue_brand(label["manufacturer"]):
            raise KenvueQueryRejected(f"Label for '{name}' belongs to a Kenvue consumer brand")
        brand = label["brand_name"] or name
        pid = _product_id(store, brand) or _product_id(store, name)
        nodes: List[GraphNode] = []
        edges: List[GraphEdge] = []
        sections = label["sections"]
        if pid is None:
            pid = f"IM_{slugify(brand)}"
            props = {LABEL_PROP_MAP[k]: v[:600] for k, v in sections.items() if k in LABEL_PROP_MAP}
            props.update({"generic_name": label["generic_name"].lower(), "category": "Prescription Medicine (openFDA)",
                          "manufacturer": label["manufacturer"], "rxcui": label["rxcui"][:3], "source": "openFDA drug/label"})
            if sections.get("boxed_warning"):
                props["boxed_warning"] = sections["boxed_warning"][:600]
            nodes.append(GraphNode(id=pid, label=NodeType.Product, name=f"{brand.upper()} ({label['generic_name'].lower()})",
                                   division=IM, properties=props))
        doc_id = f"DOC_OPENFDA_{slugify(brand)}"
        url = f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={label['set_id']}"
        nodes.append(GraphNode(id=doc_id, label=NodeType.EvidenceDocument, name=f"FDA Label (openFDA SPL v{label['version']}): {brand.upper()}",
                               division=IM, properties={
                                   "doc_type": "FDA SPL (openFDA)", "spl_setid": label["set_id"], "spl_version": label["version"],
                                   "published": _fmt_date(label["effective_time"]), "source_url": url,
                                   "excerpt": " ".join(f"{k.upper()}: {v[:300]}" for k, v in sections.items() if k in
                                                       ("boxed_warning", "indications", "contraindications")),
                                   "section_texts": sections, "sections": sorted(sections)}))
        edges.append(GraphEdge(source=pid, target=doc_id, relation=EdgeType.SUPPORTED_BY_EVIDENCE, properties={"source": "openFDA drug/label"}))
        has_bw = any(True for _ in store.out_edges(pid, EdgeType.HAS_BOXED_WARNING.value)) if store.has_node(pid) else False
        if sections.get("boxed_warning") and not has_bw:
            bw_id = f"BW_{slugify(brand)}"
            nodes.append(GraphNode(id=bw_id, label=NodeType.BoxedWarning, name=f"Boxed Warning: {brand.upper()}", division=IM,
                                   properties={"warning_text": sections["boxed_warning"][:1200], "source": "openFDA drug/label"}))
            edges += [GraphEdge(source=pid, target=bw_id, relation=EdgeType.HAS_BOXED_WARNING),
                      GraphEdge(source=bw_id, target=doc_id, relation=EdgeType.SUPPORTED_BY_EVIDENCE)]

        diff = record_label(get_db(), pid, label["set_id"], label["version"], sections)
        messages = [f"openFDA label for {brand.upper()} (set {label['set_id']}, v{label['version']}, effective "
                    f"{_fmt_date(label['effective_time'])}); sections: {sorted(sections)}"]
        if diff["changes"]:
            lc_id = f"LC_{slugify(brand)}_V{slugify(label['version'] or 'X')}_{int(time.time())}"
            claims = affected_claims(get_db(), pid)
            nodes.append(GraphNode(id=lc_id, label=NodeType.LabelChange, name=f"Label Change: {brand.upper()} v{label['version']}",
                                   division=IM, properties={
                                       "severity": "critical" if diff["critical"] else "info",
                                       "sections_changed": [c["section"] for c in diff["changes"]], "changes": diff["changes"],
                                       "affected_library_claims": claims, "detected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                       "source_url": url}))
            edges.append(GraphEdge(source=pid, target=lc_id, relation=EdgeType.HAS_LABEL_CHANGE))
            messages.append(f"LABEL CHANGE detected in {[c['section'] for c in diff['changes']]}"
                            f"{' (CRITICAL)' if diff['critical'] else ''}; {len(claims)} library claims flagged for re-review")
        elif diff["first_observation"]:
            messages.append("Baseline label version recorded for change monitoring")
        else:
            messages.append("No label changes since last refresh")
        nodes, edges = store.bulk_upsert(nodes, edges)
        return _result(conn.source, "ok", messages, nodes, edges, {"product_id": pid, "label_changes": diff["changes"],
                                                                  "watermark": label["effective_time"]})

    return await _tracked(conn.source, conn.cadence, actor, run)


# --------------------------------------------------------------------------- FAERS disproportionality
async def sync_faers(store, name: str, top_n: int = 5, client: Optional[httpx.AsyncClient] = None, actor: Optional[str] = None) -> SyncResult:
    conn = DrugEventConnector(client)

    async def run() -> SyncResult:
        pid = _product_id(store, name)
        if pid is None:
            return _result(conn.source, "not-found", [f"'{name}' is not a known J&J product in the graph; ingest its label first"])
        data = await conn.fetch_signals(name, top_n)
        if not data["signals"]:
            return _result(conn.source, "not-found", [f"No FAERS reports found for '{name}'"])
        brand = store.graph.nodes[pid]["name"].split(" (")[0]
        nodes, edges = [], []
        for s in data["signals"]:
            sid = f"SIG_{slugify(brand)}_{slugify(s['reaction'])}"
            nodes.append(GraphNode(id=sid, label=NodeType.SafetySignal, name=f"FAERS: {brand} - {s['reaction']}",
                                   division=store.graph.nodes[pid].get("division"), properties={
                                       **s, "drug_reports_total": data["drug_total"], "faers_total": data["all_total"],
                                       "method": "PRR/ROR (Evans 2001 criteria)", "source": "openFDA drug/event (FAERS)",
                                       "caveat": "Spontaneous reports; disproportionality is hypothesis-generating, not causal"}))
            edges.append(GraphEdge(source=pid, target=sid, relation=EdgeType.HAS_SAFETY_SIGNAL,
                                   properties={"prr": round(s["prr"], 2), "is_signal": s["is_signal"]}))
        nodes, edges = store.bulk_upsert(nodes, edges)
        flagged = [s["reaction"] for s in data["signals"] if s["is_signal"]]
        return _result(conn.source, "ok", [f"FAERS: {data['drug_total']:,} reports for {brand}; disproportionality signals: {flagged or 'none'}"],
                       nodes, edges, {"signals": data["signals"]})

    return await _tracked(conn.source, conn.cadence, actor, run)


# --------------------------------------------------------------------------- recalls
async def sync_recalls(store, name: str, kind: str = "drug", client: Optional[httpx.AsyncClient] = None, actor: Optional[str] = None) -> SyncResult:
    conn = EnforcementConnector(kind, client)

    async def run() -> SyncResult:
        pid = _product_id(store, name)
        recalls = await conn.fetch(name)
        if not recalls:
            return _result(conn.source, "not-found", [f"No J&J {kind} enforcement reports found for '{name}'"])
        nodes, edges = [], []
        for r in recalls:
            rid = f"RECALL_{slugify(r['recall_number'] or uuid.uuid4().hex[:8])}"
            nodes.append(GraphNode(id=rid, label=NodeType.Recall, name=f"{r['classification']} Recall {r['recall_number']}: {name}",
                                   division=MT if kind == "device" else IM, properties={**r, "source": f"openFDA {kind}/enforcement"}))
            if pid:
                edges.append(GraphEdge(source=pid, target=rid, relation=EdgeType.HAS_RECALL))
        nodes, edges = store.bulk_upsert(nodes, edges)
        return _result(conn.source, "ok", [f"{len(recalls)} J&J {kind} recall(s) for '{name}'"], nodes, edges)

    return await _tracked(conn.source, conn.cadence, actor, run)


# --------------------------------------------------------------------------- GUDID + MAUDE (MedTech)
def _medtech_franchise(text: str) -> Optional[str]:
    t = text.lower()
    return next((fr for fr, kws in MEDTECH_SPECIALTIES.items() if any(k in t for k in kws)), None)


async def sync_gudid(store, brand: str, client: Optional[httpx.AsyncClient] = None, actor: Optional[str] = None) -> SyncResult:
    conn = DeviceUDIConnector(client)

    async def run() -> SyncResult:
        devices = await conn.fetch(brand, limit=50)
        if not devices:
            return _result(conn.source, "not-found", [f"No J&J device records in AccessGUDID for '{brand}'"])
        products = [ScrapedProduct(name=d["brand_name"], division=MT,
                                   franchise=_medtech_franchise(f"{d['brand_name']} {d['company_name']} {d['gmdn_term'] or ''}"),
                                   description=d["gmdn_definition"] or d["description"] or d["gmdn_term"],
                                   source_url="https://accessgudid.nlm.nih.gov/devices/" + (d["primary_di"] or "")) for d in devices]
        nodes, edges = scraped_to_graph(products)
        nodes, edges = reconcile_with_existing(nodes, edges, store.graph.nodes(data=True))
        by_brand = {d["brand_name"].upper(): d for d in devices}
        out_nodes = []
        for n in nodes:
            d = by_brand.get(n.name.upper())
            if d is None:
                rid = _product_id(store, n.name)
                d = next((v for k, v in by_brand.items() if rid and rid == n.id), None)
            if d:
                n.properties.update({"gudid_primary_di": d["primary_di"], "gmdn_term": d["gmdn_term"], "fda_product_codes": d["product_codes"],
                                     "device_company": d["company_name"], "model_numbers": [m for m in d["models"] if m][:10],
                                     "source": "AccessGUDID (openFDA device/udi)"})
                n.properties.pop("scraped", None)
            out_nodes.append(n)
        nodes, edges = store.bulk_upsert(out_nodes, edges)
        return _result(conn.source, "ok", [f"AccessGUDID: {len(devices)} J&J device brand(s) for '{brand}' "
                                           f"({', '.join(d['company_name'] for d in devices[:3])})"], nodes, edges)

    return await _tracked(conn.source, conn.cadence, actor, run)


async def sync_maude(store, brand: str, client: Optional[httpx.AsyncClient] = None, actor: Optional[str] = None) -> SyncResult:
    conn = DeviceEventConnector(client)

    async def run() -> SyncResult:
        counts = await conn.fetch_counts(brand)
        pid = _product_id(store, brand)
        if not counts:
            return _result(conn.source, "not-found", [f"No MAUDE reports for '{brand}'"])
        nodes: List[GraphNode] = []
        if pid:
            d = store.graph.nodes[pid]
            nodes, _ = store.bulk_upsert([GraphNode(id=pid, label=d["label"], name=d["name"], division=d.get("division"), franchise=d.get("franchise"),
                                                    properties={"maude_event_counts": {k or "Unspecified": v for k, v in counts.items()}})], [])
        return _result(conn.source, "ok", [f"MAUDE event types for '{brand}': {counts}" + ("" if pid else " (no matching graph product)")],
                       nodes, [], {"counts": counts})

    return await _tracked(conn.source, conn.cadence, actor, run)


# --------------------------------------------------------------------------- trials / literature
async def sync_trials(store, name: str, limit: int = 5, client: Optional[httpx.AsyncClient] = None, actor: Optional[str] = None) -> SyncResult:
    conn = ClinicalTrialsConnector(client)

    async def run() -> SyncResult:
        pid = _product_id(store, name)
        studies = await conn.fetch(name, limit)
        if not studies:
            return _result(conn.source, "not-found", [f"No ClinicalTrials.gov studies for '{name}'"])
        nodes, edges = [], []
        for s in studies:
            if not s["nct_id"]:
                continue
            tid = f"CT_{s['nct_id']}"
            nodes.append(GraphNode(id=tid, label=NodeType.ClinicalTrial, name=f"{s['nct_id']}: {s['title']}"[:220],
                                   division=store.graph.nodes[pid].get("division") if pid else IM, properties={**s, "source_url": s["url"]}))
            if pid:
                edges.append(GraphEdge(source=pid, target=tid, relation=EdgeType.STUDIED_IN, properties={"phase": ",".join(s["phases"])}))
        nodes, edges = store.bulk_upsert(nodes, edges)
        return _result(conn.source, "ok", [f"ClinicalTrials.gov: {len(nodes)} studies for '{name}'"], nodes, edges)

    return await _tracked(conn.source, conn.cadence, actor, run)


async def sync_pubmed(store, name: str, limit: int = 5, client: Optional[httpx.AsyncClient] = None, actor: Optional[str] = None) -> SyncResult:
    conn = PubMedConnector(client)

    async def run() -> SyncResult:
        pid = _product_id(store, name)
        term = name
        if pid and store.graph.nodes[pid].get("properties", {}).get("generic_name"):
            term = f"{name} OR {store.graph.nodes[pid]['properties']['generic_name'].split(' and ')[0]}"
        pubs = await conn.fetch(term, limit)
        if not pubs:
            return _result(conn.source, "not-found", [f"No PubMed articles for '{name}'"])
        nodes, edges = [], []
        for p in pubs:
            nid = f"PMID_{p['pmid']}"
            nodes.append(GraphNode(id=nid, label=NodeType.Publication, name=p["title"][:220],
                                   division=store.graph.nodes[pid].get("division") if pid else None,
                                   properties={**p, "source_url": p["url"], "published": p["pubdate"], "doc_type": "Peer-reviewed publication"}))
            if pid:
                edges.append(GraphEdge(source=pid, target=nid, relation=EdgeType.CITED_IN))
        nodes, edges = store.bulk_upsert(nodes, edges)
        return _result(conn.source, "ok", [f"PubMed: {len(nodes)} articles for '{term}'"], nodes, edges)

    return await _tracked(conn.source, conn.cadence, actor, run)


SOURCE_SYNCS: Dict[str, Callable[..., Any]] = {
    "openfda_label": sync_label,
    "faers": sync_faers,
    "drug_recalls": lambda store, name, **kw: sync_recalls(store, name, "drug", **kw),
    "device_recalls": lambda store, name, **kw: sync_recalls(store, name, "device", **kw),
    "gudid": sync_gudid,
    "maude": sync_maude,
    "clinicaltrials": sync_trials,
    "pubmed": sync_pubmed,
}


# --------------------------------------------------------------------------- two-phase dynamic expansion
_jobs: Dict[str, Dict[str, Any]] = {}
_jobs_lock = threading.Lock()


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    with _jobs_lock:
        job = _jobs.get(job_id)
        return None if job is None else {**job, "steps": list(job["steps"])}


def _update_job(job_id: str, **kw: Any) -> None:
    with _jobs_lock:
        _jobs[job_id].update(kw)


async def expand_phase1(store, name: str, division: str = IM, client: Optional[httpx.AsyncClient] = None, actor: Optional[str] = None) -> Dict[str, Any]:
    """Synchronous identity resolution: existing node, else RxNorm (drugs) / GUDID (devices)."""
    if is_kenvue_brand(name):
        raise KenvueQueryRejected(f"'{name}' is a Kenvue consumer-health brand (outside the J&J portfolio)")
    pid = _product_id(store, name)
    if pid:
        return {"product_id": pid, "created": False, "method": "graph", "name": store.graph.nodes[pid]["name"]}
    if division == MT:
        res = await sync_gudid(store, name, client=client, actor=actor)
        pid = next((n.id for n in res["added_nodes"]), None)
        return {"product_id": pid, "created": bool(pid), "method": "gudid", "name": name, "messages": res["messages"]}
    rx = await RxNormConnector(client).resolve(name)
    if not rx or not rx.get("rxcui"):
        return {"product_id": None, "created": False, "method": "rxnorm", "name": name,
                "suggestions": (rx or {}).get("suggestions", []), "messages": [f"RxNorm could not resolve '{name}'"]}
    canonical = rx["name"] or name
    if is_kenvue_brand(canonical):
        raise KenvueQueryRejected(f"'{canonical}' is a Kenvue consumer-health brand")
    pid = _product_id(store, canonical)
    if pid:
        return {"product_id": pid, "created": False, "method": f"rxnorm-{rx['method']}", "name": canonical, "rxcui": rx["rxcui"]}
    pid = f"IM_{slugify(canonical)}"
    store.bulk_upsert([GraphNode(id=pid, label=NodeType.Product, name=canonical.upper(), division=IM,
                                 properties={"rxcui": rx["rxcui"], "rxnorm_tty": rx["tty"], "category": "Prescription Medicine (RxNorm)",
                                             "source": "NLM RxNorm", "aliases": [name]})], [])
    get_db().audit("expand.phase1", pid, {"query": name, "rxcui": rx["rxcui"]}, actor)
    return {"product_id": pid, "created": True, "method": f"rxnorm-{rx['method']}", "name": canonical, "rxcui": rx["rxcui"]}


async def _phase2(store, job_id: str, name: str, division: str, actor: Optional[str]) -> None:
    steps: List[Tuple[str, Callable[..., Any]]] = (
        [("gudid", sync_gudid), ("maude", sync_maude), ("device_recalls", SOURCE_SYNCS["device_recalls"]), ("clinicaltrials", sync_trials),
         ("pubmed", sync_pubmed)] if division == MT else
        [("openfda_label", sync_label), ("faers", sync_faers), ("drug_recalls", SOURCE_SYNCS["drug_recalls"]),
         ("clinicaltrials", sync_trials), ("pubmed", sync_pubmed)])
    for step, fn in steps:
        _update_job(job_id, current_step=step)
        res = await fn(store, name, actor=actor)
        with _jobs_lock:
            _jobs[job_id]["steps"].append({"step": step, "status": res["status"], "messages": res["messages"],
                                           "added_nodes": len(res["added_nodes"]), "added_edges": len(res["added_edges"])})
    _update_job(job_id, status="complete", current_step=None, finished_at=time.time())


def _new_job(name: str, division: str, phase1: Dict[str, Any]) -> str:
    job_id = uuid.uuid4().hex[:12]
    with _jobs_lock:
        _jobs[job_id] = {"job_id": job_id, "query": name, "division": division, "phase1": phase1, "status": "running",
                         "current_step": None, "steps": [], "started_at": time.time(), "finished_at": None}
    return job_id


async def start_expansion(store, name: str, division: str = IM, actor: Optional[str] = None, background: bool = True) -> Dict[str, Any]:
    """Phase 1 (identity) runs inline; phase 2 (evidence fan-out) runs in a daemon thread unless ``background=False``."""
    phase1 = await expand_phase1(store, name, division, actor=actor)
    job_id = _new_job(name, division, phase1)
    if not phase1.get("product_id"):
        _update_job(job_id, status="failed", finished_at=time.time())
        return get_job(job_id)  # type: ignore[return-value]
    target = (phase1.get("name") or name).split(" (")[0].strip() or name
    if not background:
        await _phase2(store, job_id, target, division, actor)
        return get_job(job_id)  # type: ignore[return-value]

    def worker() -> None:
        try:
            asyncio.run(_phase2(store, job_id, target, division, actor))
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Expansion job %s failed", job_id)
            _update_job(job_id, status="failed", error=str(exc), finished_at=time.time())

    threading.Thread(target=worker, name=f"expand-{job_id}", daemon=True).start()
    return get_job(job_id)  # type: ignore[return-value]


# --------------------------------------------------------------------------- scheduled refresh
async def refresh_due(store, actor: Optional[str] = "scheduler", limit: int = 25) -> List[SyncResult]:
    """Refresh labels for every product that has an openFDA label document when the source is due."""
    status = {s["source"]: s for s in get_db().source_status()}
    label_state = status.get("openfda_drug_label")
    if label_state and not label_state["due"]:
        return []
    watched = [store.graph.nodes[s]["name"].split(" (")[0] for s, t, d in store.graph.edges(data=True)
               if d["relation"] == EdgeType.SUPPORTED_BY_EVIDENCE.value and t.startswith("DOC_OPENFDA_")]
    results = []
    for name in list(dict.fromkeys(watched))[:limit]:
        results.append(await sync_label(store, name, actor=actor))
    return results
