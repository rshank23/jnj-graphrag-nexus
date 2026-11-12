"""FastAPI application: CORS, lifespan seeding and REST routes."""
from __future__ import annotations

import logging
import re
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from app.agents.supervisor import get_supervisor
from app.config import get_settings
from app.graph.graph_store import GraphStore, get_graph_store, set_graph_store
from app.graph.seed_data import IM, MT, is_kenvue_brand
from app.ingestion.jnj_scraper import JnJIngestionScraper, http_verify, parse_innovative_medicine_html, parse_medtech_html, reconcile_with_existing, scraped_to_graph
from app.ingestion.pdf_extractor import FDALabelPDFExtractor, slugify
from app.models.schemas import (
    AgentQueryRequest,
    AgentQueryResponse,
    BundleRequest,
    BundleResponse,
    EdgeType,
    GraphEdge,
    GraphNode,
    IngestSyncRequest,
    IngestSyncResponse,
    NodeType,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("jnj-graphrag")
ALLOWED_SCRAPE_DOMAINS = ("jnj.com", "jnjmedtech.com", "dailymed.nlm.nih.gov")


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = get_graph_store()
    stats = store.stats()
    logger.info("Graph ready on %s backend: %s nodes / %s edges", store.backend_name, stats["node_count"], stats["edge_count"])
    yield


settings = get_settings()
app = FastAPI(title="J&J GraphRAG Nexus API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False, allow_methods=["*"], allow_headers=["*"])


def store() -> GraphStore:
    return get_graph_store()


@app.get("/api/health")
def health() -> Dict[str, Any]:
    s = store()
    stats = s.stats()
    return {
        "status": "healthy",
        "backend": "networkx+neo4j-ready",
        "active_store": s.backend_name,
        "llm_mode": settings.llm_mode,
        "node_count": stats["node_count"],
        "edge_count": stats["edge_count"],
        "sku_count": stats["sku_count"],
        "franchise_count": stats["franchise_count"],
        "division_breakdown": stats["division_breakdown"],
        "label_breakdown": stats["label_breakdown"],
    }


@app.get("/api/graph")
def graph(division: Optional[str] = Query(None), node_type: Optional[str] = Query(None), search: Optional[str] = Query(None)) -> Dict[str, Any]:
    return store().filtered_graph(division=division, node_type=node_type, search=search)


@app.get("/api/graph/ego/{node_id}")
def ego(node_id: str, hops: int = Query(2, ge=1, le=3)) -> Dict[str, Any]:
    s = store()
    if not s.has_node(node_id):
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")
    sub = s.ego_subgraph(node_id, hops)
    sub["lineage"] = s.claim_lineage(node_id)
    return sub


@app.get("/api/procedures")
def procedures() -> List[Dict[str, Any]]:
    s = store()
    return [s.node_dict(nid) for nid, d in s.graph.nodes(data=True) if d["label"] == NodeType.Procedure.value]


@app.post("/api/bundle/recommend", response_model=BundleResponse)
def bundle(req: BundleRequest) -> BundleResponse:
    try:
        return store().compute_procedural_bundle(req)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Procedure '{req.procedure_id}' not found")


@app.post("/api/agent/query", response_model=AgentQueryResponse)
def agent_query(req: AgentQueryRequest) -> AgentQueryResponse:
    return get_supervisor(store()).run(req)


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


@app.post("/api/ingest/sync", response_model=IngestSyncResponse)
async def ingest_sync(request: Request) -> IngestSyncResponse:
    req, file_bytes, filename = await _parse_ingest_request(request)
    s = store()
    scraper = JnJIngestionScraper()
    extractor = FDALabelPDFExtractor()
    mode = req.mode.lower()

    if mode == "live":
        result = await scraper.sync_all(max_pages=req.max_pages)
        nodes, edges = scraped_to_graph(result["products"])
        nodes, edges = reconcile_with_existing(nodes, edges, s.graph.nodes(data=True))
        added_n, added_e = s.bulk_upsert(nodes, edges)
        status = "ok" if added_n else "no-new-data"
        return _response(mode, status, result["messages"], result["rejected_kenvue_brands"], added_n, added_e)

    if mode == "dailymed":
        name = (req.drug_name or req.product_name or "").strip()
        if not name:
            raise HTTPException(status_code=422, detail="drug_name is required for dailymed mode")
        if is_kenvue_brand(name):
            return _response(mode, "rejected", [f"'{name}' is a Kenvue consumer-health brand (out of J&J portfolio)"], [name], [], [])
        try:
            spl = await scraper.resolve_dailymed_spl(name)
        except httpx.HTTPError as exc:
            return _response(mode, "error", [f"DailyMed unavailable: {exc}"], [], [], [])
        if not spl:
            return _response(mode, "not-found", [f"No DailyMed SPL found for '{name}'"], [], [], [])
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
                sections = extractor.split_sections(extractor.extract_text(pdf.content))
                props["sections"] = sorted(sections)
                props["excerpt"] = " ".join(f"{k.upper()}: {v[:400]}" for k, v in sections.items()) or props["excerpt"]
                messages.append(f"Downloaded label PDF and parsed sections: {sorted(sections)}")
        except Exception as exc:
            messages.append(f"Label PDF download/parse skipped: {exc}")
        doc = GraphNode(id=doc_id, label=NodeType.EvidenceDocument, name=f"DailyMed SPL: {spl.get('title') or name}"[:200], division=IM, properties=props)
        edges = [GraphEdge(source=nid, target=doc_id, relation=EdgeType.SUPPORTED_BY_EVIDENCE, properties={"source": "DailyMed v2"})
                 for nid, d in s.graph.nodes(data=True)
                 if d["label"] == NodeType.Product.value and re.search(rf"\b{re.escape(name.lower())}\b", d["name"].lower())]
        added_n, added_e = s.bulk_upsert([doc], edges)
        if not edges:
            messages.append("No existing product matched the drug name; evidence document stored standalone")
        return _response(mode, "ok", messages, [], added_n, added_e)

    if mode == "url":
        if not req.url:
            raise HTTPException(status_code=422, detail="url is required for url mode")
        host = urlparse(req.url).netloc.lower()
        if not any(host == d or host.endswith("." + d) for d in ALLOWED_SCRAPE_DOMAINS):
            raise HTTPException(status_code=422, detail=f"URL host must be one of {ALLOWED_SCRAPE_DOMAINS}")
        try:
            resp = await scraper._get(req.url)
        except httpx.HTTPError as exc:
            return _response(mode, "error", [f"Fetch failed: {exc}"], [], [], [])
        if "jnjmedtech.com" in host:
            products, rejected, _ = parse_medtech_html(resp.text, req.url)
        else:
            products, rejected = parse_innovative_medicine_html(resp.text, req.url)
        nodes, edges = scraped_to_graph(products)
        nodes, edges = reconcile_with_existing(nodes, edges, s.graph.nodes(data=True))
        added_n, added_e = s.bulk_upsert(nodes, edges)
        return _response(mode, "ok", [f"Parsed {len(products)} products from {req.url}"], rejected, added_n, added_e)

    if mode in ("text", "pdf"):
        division = req.division if req.division in (IM, MT) else IM
        name = req.product_name
        if name and is_kenvue_brand(name):
            return _response(mode, "rejected", [f"'{name}' is a Kenvue consumer-health brand (out of J&J portfolio)"], [name], [], [])
        try:
            if mode == "pdf":
                if not file_bytes:
                    raise HTTPException(status_code=422, detail="A PDF file upload is required for pdf mode")
                if filename:
                    (settings.raw_pdf_dir / re.sub(r"[^A-Za-z0-9._-]", "_", filename)).write_bytes(file_bytes)
                extraction = extractor.extract(file_bytes, product_name=name, division=division, franchise=req.franchise,
                                               doc_title=f"Uploaded Label: {filename or name}")
            else:
                if not req.product_text:
                    raise HTTPException(status_code=422, detail="product_text is required for text mode")
                extraction = extractor.extract_from_text(req.product_text, product_name=name, division=division, franchise=req.franchise)
        except ValueError as exc:
            return _response(mode, "rejected", [str(exc)], [name or ""], [], [])
        added_n, added_e = extractor.ingest(s, extraction)
        msg = f"Extracted sections {sorted(extraction.sections)} for '{extraction.product_name}'"
        return _response(mode, "ok", [msg], [], added_n, added_e)

    raise HTTPException(status_code=422, detail=f"Unknown mode '{req.mode}'. Use live, dailymed, url, text or pdf")


@app.post("/api/admin/reseed")
def reseed() -> Dict[str, Any]:
    s = GraphStore().initialize(force_reseed=True)
    set_graph_store(s)
    return {"status": "reseeded", **s.stats()}
