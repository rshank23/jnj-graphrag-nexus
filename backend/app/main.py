"""FastAPI application: CORS, lifespan seeding, auth, REST routes for GraphRAG, MLR pre-review, evidence sources and ops."""
from __future__ import annotations

import asyncio
import logging
import re
from contextlib import asynccontextmanager
from typing import Any, Awaitable, Callable, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from app.agents.supervisor import get_supervisor
from app.config import get_settings
from app.core.auth import Principal, create_api_key, ensure_bootstrap_key, get_principal, list_api_keys, require_role
from app.core.db import get_db
from app.core.docx import DOCX_MEDIA_TYPE, DocxBuilder
from app.core.telemetry import init_tracing, observe
from app.graph.graph_store import GraphStore, get_graph_store, set_graph_store
from app.graph.seed_data import IM, MT, is_kenvue_brand
from app.guardrails import sanitize_ingested_text
from app.ingestion import evidence_sync
from app.ingestion.connectors import KenvueQueryRejected
from app.ingestion.jnj_scraper import JnJIngestionScraper, http_verify, parse_innovative_medicine_html, parse_medtech_html, reconcile_with_existing, scraped_to_graph
from app.ingestion.pdf_extractor import FDALabelPDFExtractor, slugify
from app.llm.router import list_prompts
from app.mlr import library as claims_library
from app.mlr import service as mlr
from app.models.schemas import (
    AgentQueryRequest,
    AgentQueryResponse,
    ApiKeyRequest,
    BundleRequest,
    BundleResponse,
    EdgeType,
    ExpandRequest,
    FeedbackRequest,
    GraphEdge,
    GraphNode,
    IngestSyncRequest,
    IngestSyncResponse,
    MLRDecisionRequest,
    MLRReviewRequest,
    NodeType,
    SourceSyncRequest,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("jnj-graphrag")
ALLOWED_SCRAPE_DOMAINS = ("jnj.com", "jnjmedtech.com", "dailymed.nlm.nih.gov")


async def _refresh_loop(hours: float) -> None:
    while True:
        await asyncio.sleep(hours * 3600)
        try:
            results = await evidence_sync.refresh_due(get_graph_store())
            logger.info("Scheduled refresh: %d label(s) checked", len(results))
        except Exception:  # pragma: no cover - background resilience
            logger.exception("Scheduled refresh failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = get_graph_store()
    stats = store.stats()
    ensure_bootstrap_key()
    init_tracing()
    logger.info("Graph ready on %s backend: %s nodes / %s edges", store.backend_name, stats["node_count"], stats["edge_count"])
    task = asyncio.create_task(_refresh_loop(settings.auto_refresh_hours)) if settings.auto_refresh_hours > 0 else None
    yield
    if task:
        task.cancel()


settings = get_settings()
app = FastAPI(title="J&J GraphRAG Nexus API", version="1.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False, allow_methods=["*"], allow_headers=["*"])


def store() -> GraphStore:
    return get_graph_store()


# =========================================================================== core graph + agent routes
@app.get("/api/health")
def health() -> Dict[str, Any]:
    s = store()
    stats = s.stats()
    return {
        "status": "healthy",
        "backend": "networkx+neo4j-ready",
        "active_store": s.backend_name,
        "llm_mode": settings.llm_mode,
        "auth_required": settings.require_api_key,
        "node_count": stats["node_count"],
        "edge_count": stats["edge_count"],
        "sku_count": stats["sku_count"],
        "franchise_count": stats["franchise_count"],
        "division_breakdown": stats["division_breakdown"],
        "label_breakdown": stats["label_breakdown"],
    }


@app.get("/api/me")
def me(principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
    return principal.to_dict()


@app.get("/api/graph")
def graph(division: Optional[str] = Query(None), node_type: Optional[str] = Query(None), search: Optional[str] = Query(None),
          _: Principal = Depends(get_principal)) -> Dict[str, Any]:
    return store().filtered_graph(division=division, node_type=node_type, search=search)


@app.get("/api/graph/ego/{node_id}")
def ego(node_id: str, hops: int = Query(2, ge=1, le=3), _: Principal = Depends(get_principal)) -> Dict[str, Any]:
    s = store()
    if not s.has_node(node_id):
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")
    sub = s.ego_subgraph(node_id, hops)
    sub["lineage"] = s.claim_lineage(node_id)
    return sub


@app.get("/api/procedures")
def procedures(_: Principal = Depends(get_principal)) -> List[Dict[str, Any]]:
    s = store()
    return [s.node_dict(nid) for nid, d in s.graph.nodes(data=True) if d["label"] == NodeType.Procedure.value]


@app.post("/api/bundle/recommend", response_model=BundleResponse)
@observe("api.bundle_recommend")
def bundle(req: BundleRequest, _: Principal = Depends(get_principal)) -> BundleResponse:
    try:
        return store().compute_procedural_bundle(req)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Procedure '{req.procedure_id}' not found")


def bundle_docx(b: BundleResponse) -> bytes:
    doc = DocxBuilder(f"Bundle Proposal: {b.procedure_name}")
    doc.heading(f"Procedural Bundle Proposal \u2014 {b.procedure_name}", 0)
    doc.paragraph(("Annual procedure volume: ", {"bold": True}), f"{b.annual_volume:,}")
    doc.table(["Metric", "Value"], [
        ["Capital platform revenue", f"${b.baseline_capital_revenue_usd:,.0f}"],
        ["Consumables per procedure", f"${b.per_procedure_consumable_revenue_usd:,.0f}"],
        ["Annual consumable cross-sell", f"${b.annual_consumable_cross_sell_usd:,.0f}"],
        ["Total first-year deal value", f"${b.total_first_year_deal_value_usd:,.0f}"],
        ["Attachment uplift", f"{b.attachment_uplift_pct:.1f}%"],
    ], [4500, 3000])
    for title, items in (("Capital platforms", b.capital_platforms), ("Software modules", b.software_modules),
                         ("Procedural catheters & sheaths", b.procedural_catheters_and_sheaths),
                         ("Post-op Ethicon consumables", b.post_op_ethicon_consumables)):
        if not items:
            continue
        doc.heading(title, 2)
        doc.table(["Item", "Role in procedure", "Unit price", "Clinical claim (evidence)"],
                  [[i.name, i.role_in_procedure, f"${i.unit_price_usd:,.0f}", f"{i.clinical_claim or '-'}"
                    + (f" [{i.evidence_doc_id}]" if i.evidence_doc_id else "")] for i in items], [2300, 2300, 1200, 3200])
    doc.paragraph(("Pricing is illustrative list pricing for POC purposes. Clinical claims are traced to evidence documents in the "
                   "GraphRAG Nexus knowledge graph; confirm with current IFU / labeling before customer use.",
                   {"italic": True, "color": "6B7280", "size": 8}))
    return doc.to_bytes()


@app.post("/api/bundle/export.docx")
def bundle_export(req: BundleRequest, principal: Principal = Depends(get_principal)) -> Response:
    b = bundle(req, principal)
    get_db().audit("bundle.export", req.procedure_id, {"volume": req.annual_procedure_volume}, principal.name)
    return Response(bundle_docx(b), media_type=DOCX_MEDIA_TYPE,
                    headers={"Content-Disposition": f'attachment; filename="bundle_{slugify(b.procedure_name)}.docx"'})


@app.post("/api/agent/query", response_model=AgentQueryResponse)
def agent_query(req: AgentQueryRequest, principal: Principal = Depends(get_principal)) -> AgentQueryResponse:
    return get_supervisor(store()).run(req, role=principal.role, actor=principal.name)


@app.post("/api/feedback")
def feedback(req: FeedbackRequest, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
    fid = get_db().add_feedback(req.query_id, req.rating, req.comment, principal.name)
    return {"feedback_id": fid, "status": "recorded"}


# =========================================================================== ingestion
async def _parse_ingest_request(request: Request) -> tuple[IngestSyncRequest, Optional[bytes], Optional[str]]:
    ctype = request.headers.get("content-type", "")
    if ctype.startswith("multipart/form-data") or ctype.startswith("application/x-www-form-urlencoded"):
        form = await request.form()
        data = {k: v for k, v in form.items() if isinstance(v, str) and v != ""}
        upload = form.get("file")
        file_bytes, filename = None, None
        if upload is not None and not isinstance(upload, str):
            file_bytes = await upload.read()
            filename = upload.filename
            data.setdefault("mode", "pdf")
        return IngestSyncRequest(**data), file_bytes, filename
    body = await request.body()
    return (IngestSyncRequest.model_validate_json(body) if body else IngestSyncRequest(mode="live")), None, None


def _response(mode: str, status: str, messages: List[str], rejected: List[str], nodes: List[GraphNode], edges: List[GraphEdge]) -> IngestSyncResponse:
    stats = store().stats()
    return IngestSyncResponse(mode=mode, status=status, messages=messages, rejected_kenvue_brands=rejected, added_nodes=nodes,
                              added_edges=edges, node_count=stats["node_count"], edge_count=stats["edge_count"])


def _rejected(mode: str, name: str) -> IngestSyncResponse:
    return _response(mode, "rejected", [f"'{name}' is a Kenvue consumer-health brand (out of J&J portfolio)"], [name], [], [])


class IngestContext:
    def __init__(self, req: IngestSyncRequest, file_bytes: Optional[bytes], filename: Optional[str], principal: Principal):
        self.req = req
        self.file_bytes = file_bytes
        self.filename = filename
        self.principal = principal
        self.mode = req.mode.lower()
        self.store = store()
        self.scraper = JnJIngestionScraper()
        self.extractor = FDALabelPDFExtractor()

    def name(self, what: str = "drug_name") -> str:
        name = (self.req.drug_name or self.req.product_name or "").strip()
        if not name:
            raise HTTPException(status_code=422, detail=f"{what} is required for {self.mode} mode")
        return name


async def _ingest_live(ctx: IngestContext) -> IngestSyncResponse:
    result = await ctx.scraper.sync_all(max_pages=ctx.req.max_pages)
    nodes, edges = scraped_to_graph(result["products"])
    nodes, edges = reconcile_with_existing(nodes, edges, ctx.store.graph.nodes(data=True))
    added_n, added_e = ctx.store.bulk_upsert(nodes, edges)
    return _response(ctx.mode, "ok" if added_n else "no-new-data", result["messages"], result["rejected_kenvue_brands"], added_n, added_e)


async def _ingest_dailymed(ctx: IngestContext) -> IngestSyncResponse:
    name = ctx.name()
    if is_kenvue_brand(name):
        return _rejected(ctx.mode, name)
    try:
        spl = await ctx.scraper.resolve_dailymed_spl(name)
    except httpx.HTTPError as exc:
        return _response(ctx.mode, "error", [f"DailyMed unavailable: {exc}"], [], [], [])
    if not spl:
        return _response(ctx.mode, "not-found", [f"No DailyMed SPL found for '{name}'"], [], [], [])
    doc_id = f"DOC_DAILYMED_{slugify(name)}"
    props: Dict[str, Any] = {"doc_type": "FDA SPL (DailyMed)", "spl_setid": spl["spl_setid"], "published": spl["published_date"],
                             "source_url": spl["label_url"], "pdf_url": spl["pdf_url"], "excerpt": spl.get("title") or ""}
    messages = [f"Resolved DailyMed SPL setid {spl['spl_setid']} (published {spl['published_date']})"]
    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds, follow_redirects=True, verify=http_verify()) as client:
            pdf = await client.get(spl["pdf_url"])
            pdf.raise_for_status()
        if pdf.content[:4] == b"%PDF":
            path = settings.raw_pdf_dir / f"{slugify(name)}_{spl['spl_setid']}.pdf"
            path.write_bytes(pdf.content)
            text, removed = sanitize_ingested_text(ctx.extractor.extract_text(pdf.content))
            sections = ctx.extractor.split_sections(text)
            props["sections"] = sorted(sections)
            props["section_texts"] = {k.lower().replace(" ", "_"): v[:4000] for k, v in sections.items()}
            props["excerpt"] = " ".join(f"{k.upper()}: {v[:400]}" for k, v in sections.items()) or props["excerpt"]
            messages.append(f"Downloaded label PDF and parsed sections: {sorted(sections)}")
            if removed:
                messages.append(f"Sanitized {len(removed)} line(s) containing instruction-like text")
    except Exception as exc:
        messages.append(f"Label PDF download/parse skipped: {exc}")
    doc = GraphNode(id=doc_id, label=NodeType.EvidenceDocument, name=f"DailyMed SPL: {spl.get('title') or name}"[:200], division=IM, properties=props)
    edges = [GraphEdge(source=nid, target=doc_id, relation=EdgeType.SUPPORTED_BY_EVIDENCE, properties={"source": "DailyMed v2"})
             for nid, d in ctx.store.graph.nodes(data=True)
             if d["label"] == NodeType.Product.value and re.search(rf"\b{re.escape(name.lower())}\b", d["name"].lower())]
    added_n, added_e = ctx.store.bulk_upsert([doc], edges)
    if not edges:
        messages.append("No existing product matched the drug name; evidence document stored standalone")
    return _response(ctx.mode, "ok", messages, [], added_n, added_e)


async def _ingest_url(ctx: IngestContext) -> IngestSyncResponse:
    url = ctx.req.url
    if not url:
        raise HTTPException(status_code=422, detail="url is required for url mode")
    host = urlparse(url).netloc.lower()
    if not any(host == d or host.endswith("." + d) for d in ALLOWED_SCRAPE_DOMAINS):
        raise HTTPException(status_code=422, detail=f"URL host must be one of {ALLOWED_SCRAPE_DOMAINS}")
    try:
        resp = await ctx.scraper._get(url)
    except httpx.HTTPError as exc:
        return _response(ctx.mode, "error", [f"Fetch failed: {exc}"], [], [], [])
    html, removed = sanitize_ingested_text(resp.text)
    if "jnjmedtech.com" in host:
        products, rejected, _ = parse_medtech_html(html, url)
    else:
        products, rejected = parse_innovative_medicine_html(html, url)
    nodes, edges = scraped_to_graph(products)
    nodes, edges = reconcile_with_existing(nodes, edges, ctx.store.graph.nodes(data=True))
    added_n, added_e = ctx.store.bulk_upsert(nodes, edges)
    msgs = [f"Parsed {len(products)} products from {url}"] + ([f"Sanitized {len(removed)} injection-like line(s)"] if removed else [])
    return _response(ctx.mode, "ok", msgs, rejected, added_n, added_e)


async def _ingest_text_or_pdf(ctx: IngestContext) -> IngestSyncResponse:
    req = ctx.req
    division = req.division if req.division in (IM, MT) else IM
    name = req.product_name
    if name and is_kenvue_brand(name):
        return _rejected(ctx.mode, name)
    try:
        if ctx.mode == "pdf":
            if not ctx.file_bytes:
                raise HTTPException(status_code=422, detail="A PDF file upload is required for pdf mode")
            if ctx.filename:
                (settings.raw_pdf_dir / re.sub(r"[^A-Za-z0-9._-]", "_", ctx.filename)).write_bytes(ctx.file_bytes)
            raw = ctx.extractor.extract_text(ctx.file_bytes)
            title = f"Uploaded Label: {ctx.filename or name}"
        else:
            if not req.product_text:
                raise HTTPException(status_code=422, detail="product_text is required for text mode")
            raw, title = req.product_text, None
        text, removed = sanitize_ingested_text(raw)
        kwargs: Dict[str, Any] = {"division": division, "franchise": req.franchise}
        if title:
            kwargs["doc_title"] = title
        extraction = ctx.extractor.extract_from_text(text, product_name=name, **kwargs)
    except ValueError as exc:
        return _response(ctx.mode, "rejected", [str(exc)], [name or ""], [], [])
    added_n, added_e = ctx.extractor.ingest(ctx.store, extraction)
    msgs = [f"Extracted sections {sorted(extraction.sections)} for '{extraction.product_name}'"]
    if removed:
        msgs.append(f"Sanitized {len(removed)} line(s) containing instruction-like text (indirect prompt-injection defence)")
    get_db().audit("ingest", ctx.mode, {"product": extraction.product_name, "nodes": [n.id for n in added_n]}, ctx.principal.name)
    return _response(ctx.mode, "ok", msgs, [], added_n, added_e)


async def _ingest_evidence(ctx: IngestContext) -> IngestSyncResponse:
    name = ctx.name()
    if is_kenvue_brand(name):
        return _rejected(ctx.mode, name)
    res = await evidence_sync.SOURCE_SYNCS[ctx.mode](ctx.store, name, actor=ctx.principal.name)
    return _response(ctx.mode, res["status"], res["messages"], [name] if res["status"] == "rejected" else [], res["added_nodes"], res["added_edges"])


async def _ingest_expand(ctx: IngestContext) -> IngestSyncResponse:
    name = ctx.name("product_name")
    division = ctx.req.division if ctx.req.division in (IM, MT) else IM
    try:
        job = await evidence_sync.start_expansion(ctx.store, name, division, actor=ctx.principal.name, background=False)
    except KenvueQueryRejected:
        return _rejected(ctx.mode, name)
    msgs = [f"Phase 1 ({job['phase1']['method']}): {job['phase1'].get('product_id') or 'unresolved'}"]
    msgs += [f"{st['step']}: {st['status']} (+{st['added_nodes']} nodes) {'; '.join(st['messages'])}" for st in job["steps"]]
    stats = ctx.store.stats()
    return IngestSyncResponse(mode=ctx.mode, status=job["status"], messages=msgs, rejected_kenvue_brands=[], added_nodes=[], added_edges=[],
                              node_count=stats["node_count"], edge_count=stats["edge_count"])


INGEST_HANDLERS: Dict[str, Callable[[IngestContext], Awaitable[IngestSyncResponse]]] = {
    "live": _ingest_live, "dailymed": _ingest_dailymed, "url": _ingest_url, "text": _ingest_text_or_pdf, "pdf": _ingest_text_or_pdf,
    "expand": _ingest_expand, **{m: _ingest_evidence for m in evidence_sync.SOURCE_SYNCS},
}


@app.post("/api/ingest/sync", response_model=IngestSyncResponse)
async def ingest_sync(request: Request, principal: Principal = Depends(get_principal)) -> IngestSyncResponse:
    req, file_bytes, filename = await _parse_ingest_request(request)
    handler = INGEST_HANDLERS.get(req.mode.lower())
    if handler is None:
        raise HTTPException(status_code=422, detail=f"Unknown mode '{req.mode}'. Use one of {sorted(INGEST_HANDLERS)}")
    return await handler(IngestContext(req, file_bytes, filename, principal))


# =========================================================================== evidence sources / expansion
@app.get("/api/sources/status")
def sources_status(_: Principal = Depends(get_principal)) -> Dict[str, Any]:
    known = {"openfda_drug_label": "weekly", "openfda_faers": "weekly", "openfda_drug_enforcement": "weekly",
             "openfda_device_enforcement": "weekly", "openfda_gudid": "monthly", "openfda_maude": "weekly",
             "clinicaltrials_gov": "weekly", "pubmed": "weekly"}
    rows = {r["source"]: r for r in get_db().source_status()}
    out = [rows.get(src, {"source": src, "cadence": cad, "last_success": None, "last_error": None, "items": 0, "age_hours": None,
                          "due": True, "status": "never"}) for src, cad in known.items()]
    out += [r for s, r in rows.items() if s not in known]
    return {"sources": out, "sync_modes": sorted(evidence_sync.SOURCE_SYNCS)}


@app.post("/api/sources/sync/{source}")
async def source_sync(source: str, req: SourceSyncRequest, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
    fn = evidence_sync.SOURCE_SYNCS.get(source)
    if fn is None:
        raise HTTPException(status_code=404, detail=f"Unknown source '{source}'. Use one of {sorted(evidence_sync.SOURCE_SYNCS)}")
    if is_kenvue_brand(req.name):
        raise HTTPException(status_code=422, detail=f"'{req.name}' is a Kenvue consumer-health brand (out of J&J portfolio)")
    res = await fn(store(), req.name, actor=principal.name)
    return {**res, "added_nodes": [n.model_dump() for n in res["added_nodes"]], "added_edges": [e.model_dump() for e in res["added_edges"]]}


@app.post("/api/sources/refresh")
async def sources_refresh(principal: Principal = Depends(require_role("admin", "mlr", "medical"))) -> Dict[str, Any]:
    results = await evidence_sync.refresh_due(store(), actor=principal.name)
    return {"refreshed": len(results), "results": [{"source": r["source"], "status": r["status"], "messages": r["messages"],
                                                    "label_changes": r.get("label_changes", [])} for r in results]}


@app.post("/api/expand")
async def expand(req: ExpandRequest, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
    division = req.division if req.division in (IM, MT) else IM
    try:
        return await evidence_sync.start_expansion(store(), req.name, division, actor=principal.name, background=req.background)
    except KenvueQueryRejected as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.get("/api/expand/{job_id}")
def expand_status(job_id: str, _: Principal = Depends(get_principal)) -> Dict[str, Any]:
    job = evidence_sync.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job")
    return job


# =========================================================================== MLR pre-review
@app.post("/api/mlr/review")
def mlr_review(req: MLRReviewRequest, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
    return mlr.run_review(store(), req.text, req.title, principal.name, use_llm=req.use_llm)


@app.get("/api/mlr/reviews")
def mlr_reviews(_: Principal = Depends(get_principal)) -> List[Dict[str, Any]]:
    return mlr.list_reviews()


@app.get("/api/mlr/library")
def mlr_library(_: Principal = Depends(get_principal)) -> List[Dict[str, Any]]:
    return claims_library.list_library(get_db())


@app.get("/api/mlr/{review_id}")
def mlr_get(review_id: str, _: Principal = Depends(get_principal)) -> Dict[str, Any]:
    review = mlr.get_review(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    return review


@app.post("/api/mlr/{review_id}/decisions")
def mlr_decide(review_id: str, req: MLRDecisionRequest, principal: Principal = Depends(require_role("mlr", "medical"))) -> Dict[str, Any]:
    try:
        return mlr.record_decision(review_id, req.finding_id, req.decision, req.rationale, principal.name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Not found: {exc}")


@app.post("/api/mlr/{review_id}/claims/{claim_id}/approve")
def mlr_approve_claim(review_id: str, claim_id: str, principal: Principal = Depends(require_role("mlr", "medical"))) -> Dict[str, Any]:
    try:
        return mlr.approve_claim(review_id, claim_id, principal.name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Not found: {exc}")


@app.get("/api/mlr/{review_id}/export.docx")
def mlr_export(review_id: str, principal: Principal = Depends(get_principal)) -> Response:
    review = mlr.get_review(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    get_db().audit("mlr.export", review_id, {}, principal.name)
    return Response(mlr.review_docx(review), media_type=DOCX_MEDIA_TYPE,
                    headers={"Content-Disposition": f'attachment; filename="mlr_review_{review_id}.docx"'})


# =========================================================================== ops: usage, audit, eval, prompts, keys
@app.get("/api/metrics/usage")
def usage(_: Principal = Depends(get_principal)) -> Dict[str, Any]:
    return get_db().usage_summary()


@app.get("/api/audit")
def audit(limit: int = Query(100, ge=1, le=1000), _: Principal = Depends(require_role("admin", "mlr"))) -> Dict[str, Any]:
    db = get_db()
    return {"entries": db.query("SELECT id, ts, actor, action, target, detail, hash FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)),
            "chain": db.verify_audit_chain()}


@app.get("/api/audit/verify")
def audit_verify(_: Principal = Depends(get_principal)) -> Dict[str, Any]:
    return get_db().verify_audit_chain()


@app.post("/api/eval/run")
def eval_run(_: Principal = Depends(get_principal)) -> Dict[str, Any]:
    from app.evals.run_eval import run_eval

    return run_eval(store())


@app.get("/api/prompts")
def prompts(_: Principal = Depends(get_principal)) -> List[Dict[str, str]]:
    return list_prompts()


@app.post("/api/admin/keys")
def admin_create_key(req: ApiKeyRequest, _: Principal = Depends(require_role("admin"))) -> Dict[str, Any]:
    return create_api_key(req.name, req.role, req.tier, req.monthly_limit)


@app.get("/api/admin/keys")
def admin_list_keys(_: Principal = Depends(require_role("admin"))) -> List[Dict[str, Any]]:
    return list_api_keys()


@app.post("/api/admin/reseed")
def reseed(principal: Principal = Depends(require_role("admin", "medical"))) -> Dict[str, Any]:
    s = GraphStore().initialize(force_reseed=True)
    set_graph_store(s)
    get_db().audit("admin.reseed", None, s.stats(), principal.name)
    return {"status": "reseeded", **s.stats()}
