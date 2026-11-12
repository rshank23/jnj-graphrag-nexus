"""End-to-end tests: Kenvue filter, graph traversal, BOM math, hybrid GraphRAG, LangGraph routing, ingestion and FastAPI."""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.agents.supervisor import SupervisorRunner
from app.graph.graph_store import GraphStore, KenvueBrandRejected, set_graph_store
from app.graph.seed_data import KENVUE_BRANDS, is_kenvue_brand
from app.ingestion.jnj_scraper import (JnJIngestionScraper, parse_innovative_medicine_html, parse_medtech_html,
                                       reconcile_with_existing, scraped_to_graph)
from app.ingestion.pdf_extractor import FDALabelPDFExtractor
from app.models.schemas import AgentQueryRequest, BundleRequest, GraphNode, NodeType
from app.rag.hybrid_retriever import HybridGraphRetriever

PRESET_QUERIES = {
    "medtech_bundler": "Build a complete end-to-end J&J MedTech procedural bundle for Atrial Fibrillation ablation including 3D CT segmentation modules and post-op infection control.",
    "pharma_clinical": "How do OPSYNVI, OPSUMIT, and UPTRAVI work together across PAH biological pathways, and what are the strict contraindications?",
    "regulatory_auditor": "Audit the clinical efficacy claims and 2026 trial data for ICOTYDE, RYBREVANT FASPRO, and CARVYKTI with FDA label provenance.",
}


@pytest.fixture()
def store(tmp_path) -> GraphStore:
    s = GraphStore(graph_path=tmp_path / "graph.json", use_neo4j=False).initialize()
    set_graph_store(s)
    return s


@pytest.fixture()
def client(store) -> TestClient:
    from app.main import app

    with TestClient(app) as c:
        yield c


# --------------------------------------------------------------------------- Kenvue boundary
@pytest.mark.parametrize("name", ["Tylenol", "Listerine", "Band-Aid", "BAND-AID Brand Adhesive Bandages", "TYLENOL Extra Strength",
                                  "Johnson's Baby Shampoo", "Clean & Clear Foaming Wash", "Neutrogena Hydro Boost"])
def test_kenvue_brands_rejected(name):
    assert is_kenvue_brand(name)


@pytest.mark.parametrize("name", ["CARVYKTI (ciltacabtagene autoleucel)", "TREMFYA (guselkumab)", "CARTO 3 System V8",
                                  "BIOPATCH Protective Disk with CHG", "Bandage scissors"])
def test_jnj_portfolio_not_rejected(name):
    assert not is_kenvue_brand(name)


def test_graph_store_refuses_kenvue_and_seed_is_clean(store):
    with pytest.raises(KenvueBrandRejected):
        store.upsert_node(GraphNode(id="X_TYLENOL", label=NodeType.Product, name="Tylenol", division="Consumer"))
    assert not store.has_node("X_TYLENOL")
    assert not any(is_kenvue_brand(n.name) for n in store.all_nodes())
    assert len(KENVUE_BRANDS) == 11


def test_scraper_parser_filters_kenvue():
    html = """
    <div class="product-card"><h3>CARVYKTI® (ciltacabtagene autoleucel)</h3><p>Oncology. Boxed Warning.</p>
      <a href="/files/carvykti-pi.pdf">Full Prescribing Information</a></div>
    <div class="product-card"><h3>TYLENOL®</h3><p>Pain relief</p></div>
    <div class="product-card"><h3>LISTERINE</h3><p>Mouthwash</p></div>
    <div class="product-card"><h3>Band-Aid</h3><p>Bandages</p></div>
    """
    products, rejected = parse_innovative_medicine_html(html)
    assert [p.name for p in products] == ["CARVYKTI (ciltacabtagene autoleucel)"]
    p = products[0]
    assert p.generic_name == "ciltacabtagene autoleucel" and p.franchise == "Oncology" and p.has_boxed_warning
    assert p.prescribing_info_url.endswith("/files/carvykti-pi.pdf")
    assert set(rejected) == {"TYLENOL", "LISTERINE", "Band-Aid"}


def test_live_jnj_product_search_markup_reconciles_with_curated_nodes(store):
    html = """
    <ul><li class="SearchResultsModule-results-item"><bsp-accordion class="ProductSearchPromo" id="carvykti">
      <div class="ProductSearchPromo-title">CARVYKTI®</div>
      <div class="ProductSearchPromo-description">(ciltacabtagene autoleucel; cilta-cel)</div>
      <div class="ProductSearchPromo-tags"><div class="ProductSearchPromo-tags-item"><span class="Link">Oncology</span></div></div>
      <div class="ProductSearchPromo-downloads"><ul>
        <li><a href="https://www.jnjlabels.com/pi/CARVYKTI-pi.pdf">Full Prescribing Information</a></li>
        <li><a href="https://www.jnjlabels.com/pi/CARVYKTI-pi-es.pdf">Full Prescribing Information (Español)</a></li>
      </ul></div></bsp-accordion></li>
    <li class="SearchResultsModule-results-item"><bsp-accordion class="ProductSearchPromo" id="newdrug">
      <div class="ProductSearchPromo-title">NOVELTRA™</div>
      <div class="ProductSearchPromo-description">(novelumab)</div>
      <div class="ProductSearchPromo-tags"><div class="ProductSearchPromo-tags-item"><span class="Link">Immunology</span></div></div>
    </bsp-accordion></li>
    <li class="SearchResultsModule-results-item"><bsp-accordion class="ProductSearchPromo" id="tylenol">
      <div class="ProductSearchPromo-title">TYLENOL®</div></bsp-accordion></li></ul>
    """
    products, rejected = parse_innovative_medicine_html(html)
    assert [p.name for p in products] == ["CARVYKTI", "NOVELTRA"] and rejected == ["TYLENOL"]
    carvykti = products[0]
    assert carvykti.generic_name == "ciltacabtagene autoleucel; cilta-cel" and carvykti.franchise == "Oncology"
    assert carvykti.prescribing_info_url.endswith("CARVYKTI-pi.pdf") and carvykti.source_url.endswith("#carvykti")

    nodes, edges = scraped_to_graph(products)
    nodes, edges = reconcile_with_existing(nodes, edges, store.graph.nodes(data=True))
    ids = {n.id for n in nodes}
    assert "IM_CARVYKTI" in ids and "SCR_IM_CARVYKTI" not in ids and "SCR_IM_NOVELTRA" in ids
    enriched = next(n for n in nodes if n.id == "IM_CARVYKTI")
    assert enriched.name == store.graph.nodes["IM_CARVYKTI"]["name"]
    assert set(enriched.properties) == {"prescribing_info_url", "jnj_source_url"}
    assert not any(e.source == "IM_CARVYKTI" for e in edges)


def test_medtech_parser_extracts_compatibility_and_pagination():
    html = """
    <article class="card"><h3>CARTO SMARTTOUCH SF Catheter</h3><p>Contact-force ablation catheter visualized on the CARTO 3 System.</p>
      <a href="/en-US/products/carto-smarttouch">Details</a></article>
    <article class="card"><h3>Neosporin</h3><p>Ointment</p></article>
    <a rel="next" href="/en-US/products/all-products/?page=2">Next</a>
    """
    products, rejected, next_url = parse_medtech_html(html)
    assert rejected == ["Neosporin"]
    assert products[0].franchise == "Electrophysiology" and "MT_CARTO_3_V8" in products[0].compatibility
    assert next_url.endswith("page=2")
    nodes, edges = scraped_to_graph(products)
    assert any(e.target == "MT_CARTO_3_V8" for e in edges)


# --------------------------------------------------------------------------- graph traversal
def test_two_hop_ego_from_afib_ablation(store):
    ego = store.ego_subgraph("PROC_AFIB_ABLATION", hops=2)
    assert "MT_BIOPATCH_CHG" in ego["one_hop"]
    assert "MT_CARTO_3_V8" in ego["one_hop"]
    assert "MT_CARTOSEG_CT" in ego["two_hop"]
    assert any(l["source"] == "MT_CARTOSEG_CT" and l["target"] == "MT_CARTO_3_V8" and l["relation"] == "INTEGRATES_WITH" for l in ego["links"])


def test_claim_lineage_traces_boxed_warning_to_spl(store):
    lin = store.claim_lineage("IM_CARVYKTI")
    assert lin["provenance_status"] == "verified"
    assert any(d["id"] == "DOC_FDA_CARVYKTI_SPL" for d in lin["evidence_documents"])
    assert any(b["id"] == "BW_CARVYKTI" for b in lin["boxed_warnings"])


def test_graph_persists_to_json(store):
    payload = json.loads(store.graph_path.read_text(encoding="utf-8"))
    assert len(payload["nodes"]) == store.graph.number_of_nodes()
    reloaded = GraphStore(graph_path=store.graph_path, use_neo4j=False)
    assert reloaded.load() and reloaded.graph.number_of_edges() == store.graph.number_of_edges()


# --------------------------------------------------------------------------- BOM math
def test_afib_bundle_roi_math(store):
    b = store.compute_procedural_bundle(BundleRequest(procedure_id="PROC_AFIB_ABLATION", annual_procedure_volume=500))
    assert [i.id for i in b.capital_platforms] == ["MT_CARTO_3_V8"]
    assert {i.id for i in b.software_modules} == {"MT_CARTOSEG_CT", "MT_CARTOMERGE", "MT_CARTO_PRIME", "MT_CARTO_ELEVATE", "MT_CARTOREPLAY"}
    assert {i.id for i in b.procedural_catheters_and_sheaths} == {"MT_CARTO_VIZIGO", "MT_ACUNAV_CRYSTAL"}
    assert [i.id for i in b.post_op_ethicon_consumables] == ["MT_BIOPATCH_CHG"]
    assert b.baseline_capital_revenue_usd == 285_000 + 45_000 + 38_000 + 32_000 + 29_000 + 22_000
    assert b.per_procedure_consumable_revenue_usd == 1_450 + 3_200 + 45
    assert b.annual_consumable_cross_sell_usd == 4_695 * 500
    assert b.total_first_year_deal_value_usd == 451_000 + 2_347_500
    assert b.attachment_uplift_pct == pytest.approx(2_347_500 / 451_000 * 100, abs=0.01)


def test_tka_bundle_and_post_op_toggle(store):
    with_post = store.compute_procedural_bundle(BundleRequest(procedure_id="PROC_TKA_ROBOTIC", annual_procedure_volume=200))
    assert with_post.per_procedure_consumable_revenue_usd == 4_900 + 140 + 180 + 65
    without = store.compute_procedural_bundle(BundleRequest(procedure_id="PROC_TKA_ROBOTIC", annual_procedure_volume=200,
                                                            include_post_op_consumables=False))
    assert without.post_op_ethicon_consumables == []
    assert without.annual_consumable_cross_sell_usd == (4_900 + 140) * 200


def test_bundle_unknown_procedure(store):
    with pytest.raises(KeyError):
        store.compute_procedural_bundle(BundleRequest(procedure_id="MT_CARTO_3_V8"))


# --------------------------------------------------------------------------- hybrid GraphRAG + LangGraph
def test_hybrid_retriever_fuses_and_expands(store):
    r = HybridGraphRetriever(store, use_transformers=False)
    out = r.retrieve("Which module auto segments 3D CT esophagus and coronary sinus anatomy?", top_k=5)
    assert "MT_CARTOSEG_CT" in out["seeds"]
    assert out["bm25_top"] and out["dense_top"] and out["rrf_top"]
    scores = [p["cross_encoder_score"] for p in out["reranked_passages"]]
    assert scores == sorted(scores, reverse=True)
    assert any(p["type"] == "graph_path" for p in out["reranked_passages"])
    assert any(n["id"] == "MT_CARTO_3_V8" for n in out["subgraph"]["nodes"])


@pytest.mark.parametrize("expected, query", list(PRESET_QUERIES.items()))
def test_supervisor_routes_to_all_three_agents(store, expected, query):
    runner = SupervisorRunner(store, HybridGraphRetriever(store, use_transformers=False))
    resp = runner.run(AgentQueryRequest(query=query))
    assert resp.routed_agent == expected
    assert resp.execution_trace[0].startswith("Supervisor Router")
    assert any(t.startswith("Domain Sub-Agent") for t in resp.execution_trace)
    assert resp.execution_trace[-1].startswith("Response Synthesizer")
    assert resp.subgraph["nodes"] and resp.citations and resp.reranked_passages
    if expected == "medtech_bundler":
        assert "CARTOSEG CT Segmentation Module" in resp.answer_markdown and "BIOPATCH" in resp.answer_markdown
    elif expected == "pharma_clinical":
        assert "riociguat" in resp.answer_markdown and "UPTRAVI" in resp.answer_markdown
    else:
        assert "Provenance coverage" in resp.answer_markdown and "DOC_FDA_CARVYKTI_SPL" in {c["id"] for c in resp.citations}


# --------------------------------------------------------------------------- ingestion
def _make_label_pdf() -> bytes:
    import pymupdf as fitz

    doc = fitz.open()
    page = doc.new_page()
    lines = [
        "ZORVENTA (testimab-xyzz) injection",
        "BOXED WARNING: SEVERE INFUSION REACTIONS",
        "Serious infusion reactions have occurred.",
        "1 INDICATIONS AND USAGE",
        "ZORVENTA is indicated for the treatment of adult patients with relapsed multiple myeloma.",
        "4 CONTRAINDICATIONS",
        "Known hypersensitivity to testimab. Concomitant use with live vaccines.",
        "12.1 Mechanism of Action",
        "Testimab is a CD38-directed cytolytic antibody.",
    ]
    y = 72
    for line in lines:
        page.insert_text((50, y), line, fontsize=10)
        y += 18
    data = doc.tobytes()
    doc.close()
    return data


def test_pdf_extractor_builds_triplets(store):
    ex = FDALabelPDFExtractor()
    extraction = ex.extract(_make_label_pdf())
    assert set(extraction.sections) == {"boxed_warning", "indications", "contraindications", "mechanism"}
    assert extraction.product_name.startswith("ZORVENTA")
    relations = {e.relation for e in extraction.edges}
    assert {"HAS_BOXED_WARNING", "INDICATED_FOR", "CONTRAINDICATED_WITH", "SUPPORTED_BY_EVIDENCE", "IN_FRANCHISE"} <= relations
    nodes, edges = ex.ingest(store, extraction)
    assert store.has_node("ING_ZORVENTA") and store.get_node("ING_ZORVENTA").franchise == "Oncology"


def test_dailymed_resolver_uses_v2_api():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/dailymed/services/v2/spls.json"
        assert request.url.params["drug_name"] == "carvykti" and request.url.params["pagesize"] == "1"
        return httpx.Response(200, json={"data": [{"setid": "abc-123", "title": "CARVYKTI suspension", "published_date": "Feb 01, 2026"}]})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await JnJIngestionScraper(client=client).resolve_dailymed_spl("carvykti")

    spl = asyncio.run(run())
    assert spl["spl_setid"] == "abc-123" and spl["published_date"] == "Feb 01, 2026"
    assert spl["pdf_url"].endswith("setId=abc-123")


# --------------------------------------------------------------------------- FastAPI
def test_api_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy" and body["backend"] == "networkx+neo4j-ready"
    assert body["node_count"] > 60 and body["edge_count"] > 100
    assert set(body["division_breakdown"]) >= {"J&J Innovative Medicine", "J&J MedTech"}


def test_api_graph_filters(client):
    r = client.get("/api/graph", params={"division": "J&J MedTech", "node_type": "Product,SoftwareModule"})
    assert r.status_code == 200
    nodes = r.json()["nodes"]
    assert nodes and all(n["division"] == "J&J MedTech" and n["label"] in ("Product", "SoftwareModule") for n in nodes)
    assert all("color" in n for n in nodes)
    assert client.get("/api/graph", params={"search": "esophagus"}).json()["nodes"]


def test_api_ego_and_procedures(client):
    r = client.get("/api/graph/ego/PROC_AFIB_ABLATION")
    assert r.status_code == 200 and "MT_CARTOSEG_CT" in r.json()["two_hop"]
    assert client.get("/api/graph/ego/NOPE").status_code == 404
    procs = {p["id"] for p in client.get("/api/procedures").json()}
    assert procs == {"PROC_AFIB_ABLATION", "PROC_TKA_ROBOTIC", "PROC_CALCIFIED_PCI"}


def test_api_bundle_recommend(client):
    r = client.post("/api/bundle/recommend", json={"procedure_id": "PROC_CALCIFIED_PCI", "annual_procedure_volume": 100})
    assert r.status_code == 200
    body = r.json()
    assert body["capital_platforms"][0]["id"] == "MT_SHOCKWAVE_IVL_GENERATOR"
    assert body["annual_consumable_cross_sell_usd"] == (4_800 + 45) * 100
    assert client.post("/api/bundle/recommend", json={"procedure_id": "BAD"}).status_code == 404


def test_api_agent_query(client):
    r = client.post("/api/agent/query", json={"query": PRESET_QUERIES["pharma_clinical"], "top_k": 5})
    assert r.status_code == 200
    body = r.json()
    assert body["routed_agent"] == "pharma_clinical" and body["latency_ms"] > 0
    assert body["subgraph"]["nodes"] and body["subgraph"]["links"]


def test_api_ingest_text_and_kenvue_rejection(client):
    r = client.post("/api/ingest/sync", json={"mode": "text", "product_name": "NEXAPRIL (nexaprilumab)",
                                              "product_text": "NEXAPRIL is indicated for the treatment of moderate-to-severe plaque psoriasis."})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and any(n["id"] == "ING_NEXAPRIL" for n in body["added_nodes"])
    r = client.post("/api/ingest/sync", json={"mode": "text", "product_name": "Tylenol", "product_text": "Pain reliever"})
    assert r.json()["status"] == "rejected" and r.json()["rejected_kenvue_brands"] == ["Tylenol"]


def test_api_ingest_pdf_upload(client, tmp_path, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "raw_pdf_dir", tmp_path)
    r = client.post("/api/ingest/sync", files={"file": ("zorventa.pdf", _make_label_pdf(), "application/pdf")}, data={"mode": "pdf"})
    assert r.status_code == 200 and r.json()["status"] == "ok"
    assert (tmp_path / "zorventa.pdf").exists()
    assert client.get("/api/graph/ego/ING_ZORVENTA").status_code == 200
