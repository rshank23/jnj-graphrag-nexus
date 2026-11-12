# J&J GraphRAG Nexus

Knowledge-graph intelligence platform for the **post-Kenvue-spinoff J&J portfolio** (J&J Innovative Medicine + J&J MedTech).
It combines a typed clinical/commercial knowledge graph, hybrid GraphRAG retrieval, a LangGraph multi-agent supervisor,
and a React control centre for procedural cross-sell bundling and claim auditing.

> Kenvue consumer-health brands (Tylenol, Listerine, Band-Aid, Neutrogena, Aveeno, …) are rejected at every ingestion path.

Everything runs **fully offline** by default. The local NetworkX store, scikit-learn vectors and deterministic
grounded generation are used automatically. Neo4j, sentence-transformers cross-encoders and OpenAI/Gemini are optional upgrades.

## Architecture

```
frontend/  Vite + React 18 + TypeScript + Tailwind
  ├─ MetricsRibbon      live SKU / edge / franchise counts, cross-sell uplift, sync button
  ├─ GraphExplorer      dependency-free canvas force graph (zoom/pan/drag, arrows, 2-hop spotlight, inspector)
  ├─ ProceduralBundler  4-tier BOM + ROI simulator driven by graph traversal
  ├─ AgentCopilot       LangGraph pipeline stepper, markdown answer, cross-encoder scores, citations
  └─ IngestionModal     live J&J scrape · DailyMed SPL · URL · free text · label PDF
        │  /api (Vite proxy)
backend/   FastAPI
  ├─ graph/seed_data.py        golden J&J dataset + Kenvue filter
  ├─ graph/graph_store.py      NetworkX read model ⇄ optional Neo4j MERGE mirror (JSON persisted)
  ├─ graph/queries.py          ego subgraph, procedural bundle math, claim lineage
  ├─ ingestion/jnj_scraper.py  jnj.com / jnjmedtech.com scraper + NIH DailyMed v2 resolver
  ├─ ingestion/pdf_extractor.py FDA label section extractor (PyMuPDF)
  ├─ rag/hybrid_retriever.py   BM25 + dense vectors → RRF → 2-hop expansion → cross-encoder rerank
  └─ agents/supervisor.py      LangGraph: router → medtech_bundler | pharma_clinical | regulatory_auditor → synthesizer
```

## Quick start

```bash
make install     # backend venv + pip install, frontend npm install
make test        # pytest backend/tests/test_end_to_end.py -v
./start.sh       # FastAPI on :8000 + Vite on :5173  (or: make dev)
```

Open http://localhost:5173. Interactive API docs are at http://localhost:8000/docs.

Windows (PowerShell) without make/bash:

```powershell
py -3.12 -m venv backend\.venv
backend\.venv\Scripts\python -m pip install -r backend\requirements.txt
cd backend; ..\backend\.venv\Scripts\python -m uvicorn app.main:app --port 8000   # terminal 1
cd frontend; npm install; npm run dev                                              # terminal 2
```

Docker (with Neo4j): `docker compose up`.

## Configuration (`backend/.env`, see `.env.example`)

| Variable | Effect |
|---|---|
| `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` | Mirror every upsert into Neo4j via `MERGE`. If unset or unreachable, the NetworkX store is used. |
| `OPENAI_API_KEY` / `GEMINI_API_KEY` | Polish the grounded answer with a hosted LLM. Without a key, the answer is generated deterministically from graph evidence. |
| `USE_TRANSFORMER_MODELS` | Use sentence-transformers bi-/cross-encoders when installed. Otherwise TF-IDF+SVD vectors and a calibrated lexical reranker are used. |

### Live sync notes

- **jnj.com Innovative Medicine:** the server-rendered `ProductSearchPromo` cards are parsed (brand, generic name, therapeutic area, PI PDF link). Products that already exist in the curated graph are only *enriched* with provenance (`prescribing_info_url`, `jnj_source_url`). Their curated name, franchise and edges are never overwritten.
- **NIH DailyMed:** resolves the latest SPL set id, downloads the label PDF, extracts its sections and links it as `SUPPORTED_BY_EVIDENCE`.
- **TLS:** HTTPS uses the OS trust store via `truststore`, so it works behind corporate TLS inspection.
- **jnjmedtech.com:** the site bot-blocks automated clients (HTTP 403). The sync reports this in `messages` and continues. Use URL, text or PDF ingestion for MedTech devices.

## REST API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Store backend, LLM mode, node/edge/SKU/franchise counts |
| GET | `/api/graph?division=&node_type=A,B&search=` | Filtered graph for visualisation |
| GET | `/api/graph/ego/{id}?hops=2` | Ego subgraph + serialized paths + claim lineage |
| GET | `/api/procedures` | Procedure nodes |
| POST | `/api/bundle/recommend` | `{procedure_id, annual_procedure_volume, include_post_op_consumables}` → 4-tier BOM + ROI |
| POST | `/api/agent/query` | `{query, top_k, max_hops}` → routed agent, trace, markdown, reranked passages, subgraph, citations |
| POST | `/api/ingest/sync` | JSON `{mode: live\|dailymed\|url\|text}` or multipart PDF upload (`mode=pdf`) |
| POST | `/api/admin/reseed` | Rebuild the graph from the golden dataset |

### Bundle financial model

```
baseline_capital   = Σ tier1 capital + Σ tier2 software           (one-time)
per_procedure      = Σ tier3 procedural + Σ tier4 post-op Ethicon
annual_cross_sell  = per_procedure × annual_volume
total_year_one     = baseline_capital + annual_cross_sell
attachment_uplift% = annual_cross_sell / baseline_capital × 100
```

Example: AFib ablation at 500 procedures/yr gives a $451,000 baseline, $4,695 per procedure, $2,347,500 annual pull-through and +520.51% uplift.

## Tests

`pytest backend/tests/test_end_to_end.py -v` covers:

- Kenvue exclusion
- Seed integrity
- 2-hop traversal (`PROC_AFIB_ABLATION` → `MT_CARTOSEG_CT` via `MT_CARTO_3_V8`, and → `MT_BIOPATCH_CHG`)
- Bundle ROI math
- Hybrid retrieval
- Supervisor routing to all three agents
- Scraper/PDF parsers
- All FastAPI endpoints

It uses FastAPI `TestClient` and runs fully offline.
