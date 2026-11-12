# J&J GraphRAG Nexus

Knowledge-graph intelligence platform for the **post-Kenvue-spinoff J&J portfolio** (J&J Innovative Medicine + J&J MedTech).
It combines a typed clinical/commercial knowledge graph, hybrid GraphRAG retrieval, a LangGraph multi-agent supervisor,
and a React control centre for procedural cross-sell bundling, **MLR pre-review of promotional assets**, and claim auditing.
The graph is continuously grounded in sanctioned public sources: openFDA labels, FAERS, recalls, GUDID, MAUDE,
ClinicalTrials.gov and PubMed. The platform also has guardrails, role-based access, a tamper-evident audit trail,
usage/cost metering, a golden-set evaluation harness and an MCP server, so other teams' AI assistants can use the graph.

> Kenvue consumer-health brands (Tylenol, Listerine, Band-Aid, Neutrogena, Aveeno, …) are rejected at every ingestion path.

Everything runs **fully offline** by default. The local NetworkX store, scikit-learn vectors and deterministic
grounded generation are used automatically. Neo4j, sentence-transformers cross-encoders and OpenAI/Gemini are optional upgrades.

## Architecture

```
frontend/  Vite + React 18 + TypeScript + Tailwind
  ├─ MetricsRibbon      live SKU / edge / franchise counts, cross-sell uplift, sync button
  ├─ GraphExplorer      dependency-free canvas force graph (zoom/pan/drag, arrows, 2-hop spotlight, inspector)
  ├─ ProceduralBundler  4-tier BOM + ROI simulator driven by graph traversal
  ├─ AgentCopilot       LangGraph pipeline stepper, risk/confidence/guardrail badges, citations, 👍/👎 feedback
  ├─ MLRReview          annotated asset, severity-ranked findings + precedents, accept/revise/dismiss, claims library, DOCX
  ├─ OpsDashboard       source freshness + sync, portfolio expansion jobs, usage/cost/satisfaction, audit chain, eval runner
  └─ IngestionModal     live J&J scrape · DailyMed SPL · URL · free text · label PDF · evidence APIs · expand
        │  /api (Vite proxy)  · X-Nexus-Role / X-Nexus-API-Key headers
backend/   FastAPI
  ├─ graph/seed_data.py        golden J&J dataset + Kenvue filter
  ├─ graph/graph_store.py      NetworkX read model ⇄ optional Neo4j MERGE mirror (JSON persisted)
  ├─ graph/queries.py          ego subgraph, procedural bundle math, claim lineage
  ├─ ingestion/connectors/     openFDA (label, FAERS, enforcement, GUDID, MAUDE), ClinicalTrials.gov, PubMed, RxNorm
  ├─ ingestion/evidence_sync.py tracked source syncs, label-change monitor, PRR/ROR signals, two-phase expansion jobs
  ├─ ingestion/jnj_scraper.py  jnj.com / jnjmedtech.com scraper + NIH DailyMed v2 resolver
  ├─ ingestion/pdf_extractor.py FDA label section extractor (PyMuPDF)
  ├─ rag/entity_resolver.py    entity resolution (exact → alias → fuzzy) before any node is created
  ├─ rag/hybrid_retriever.py   BM25 + dense (ONNX MiniLM | TF-IDF+SVD) → RRF → 2-hop expansion → rerank
  ├─ agents/supervisor.py      LangGraph: guardrails → router → 3 specialists → synthesizer (confidence, risk, scope)
  ├─ mlr/                      claim extraction, 10 compliance checks, precedents, decisions, claims library, DOCX
  ├─ core/                     http retry/TTL cache, ops SQLite (audit hash-chain, usage, feedback), auth, telemetry, DOCX
  ├─ guardrails.py             PHI redaction, prompt-injection block, scope + commercial off-label gates
  ├─ llm/router.py             Azure OpenAI → OpenAI → Gemini → local, with token/cost metering
  ├─ prompts/*.yaml            versioned prompt templates
  ├─ evals/                    40-query golden set; GraphRAG vs BM25 / dense / hybrid scorecard
  └─ mcp_server.py             Model Context Protocol (stdio JSON-RPC) server exposing graph tools
```

## Quick start

Prerequisites: Node 18+ and Python 3.10+. Then, from the repo root:

```bash
npm run dev
```

That single command works on Windows, macOS and Linux. It:

1. creates `backend/.venv` and installs Python dependencies on the first run (and again whenever `requirements.txt` changes)
2. runs `npm install` for the frontend if `node_modules` is missing
3. starts FastAPI on :8000 with hot reload and waits until `/api/health` is green
4. starts Vite on :5173

Logs from both processes appear in one terminal, prefixed `[api]` / `[web]`. Ctrl+C stops both. Running `npm run dev` inside `frontend/` does the same thing.

Open http://localhost:5173. Interactive API docs are at http://localhost:8000/docs.
Ports can be overridden with `BACKEND_PORT` / `FRONTEND_PORT`, and the Python interpreter with `PYTHON`.

Other commands: `npm test` runs the backend pytest suite (57 tests, offline). `npm run build` builds the production frontend bundle. `make install|test|backend|frontend` still work.

Docker (with Neo4j): `docker compose up`.

## Configuration (`backend/.env`, see `.env.example`)

| Variable | Effect |
|---|---|
| `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` | Mirror every upsert into Neo4j via `MERGE`. If unset or unreachable, the NetworkX store is used. |
| `OPENAI_API_KEY` / `GEMINI_API_KEY` | Polish the grounded answer with a hosted LLM. Without a key, the answer is generated deterministically from graph evidence. |
| `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT` | Preferred enterprise LLM provider. The router falls back through OpenAI, then Gemini, then the local generator. Tokens and cost are metered per call. |
| `USE_TRANSFORMER_MODELS` | Use sentence-transformers bi-/cross-encoders when installed. Otherwise TF-IDF+SVD vectors and a calibrated lexical reranker are used. |
| `ONNX_MODEL_DIR` | Torch-free MiniLM semantic embeddings (`model.onnx` + `vocab.txt`) via onnxruntime. |
| `OPENFDA_API_KEY`, `NCBI_API_KEY` | Optional. They only raise the public API rate limits. |
| `REQUIRE_API_KEY`, `BOOTSTRAP_ADMIN_KEY` | Enforce `X-Nexus-API-Key` on every request. The bootstrap key is an admin key; use it to mint per-user keys via `POST /api/admin/keys`. |
| `ENTRA_TENANT_ID`, `ENTRA_AUDIENCE` | Accept Microsoft Entra ID bearer tokens. App roles map to `commercial` / `medical` / `mlr` / `admin`. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Export OpenTelemetry spans (agent, retrieval, connector calls). |
| `MIN_ANSWER_CONFIDENCE` | Answers below this confidence are marked for human review. |
| `AUTO_REFRESH_HOURS` | When > 0, a background loop refreshes due sources (label-change monitor) on this cadence. |

### Roles

| Role | Can do |
|---|---|
| `commercial` | Query, bundle, run MLR pre-reviews. Off-label / unapproved-use content is withheld. |
| `medical` (local default) | Everything above plus off-label scientific exchange, MLR decisions, source refresh, reseed |
| `mlr` | MLR decisions, approved claims library, audit log |
| `admin` | Everything, including API-key management |

With `REQUIRE_API_KEY=false` (local demo), the role comes from the `X-Nexus-Role` header, which the header role selector in the UI sets.

## MLR pre-review

Paste promotional copy into **MLR Pre-Review** or call `POST /api/mlr/review`. The pipeline runs these steps:

1. Extracts claims (rules, optionally LLM-assisted) and links products through the entity resolver.
2. Verifies each claim against label sections and evidence in the graph.
3. Runs 10 checks: absolute claims, comparative/superlative claims, off-label indications, contraindications, unsupported cross-product combinations, missing citations, FAERS safety signals, recent label changes, safety omission and fair balance.

Each finding has a severity, a suggested revision, evidence links and the relevant FDA OPDP / 21 CFR 202.1 precedent.
Reviewers accept, revise or dismiss each finding (role-gated and audit-logged). They can also approve clean claims into a
reusable claims library and export the annotated review as DOCX for the MLR committee.

## Evidence sources and freshness

`POST /api/sources/sync/{source}` with `{"name": "TREMFYA"}`. The `source` value is one of:
`openfda_label`, `faers`, `drug_recalls`, `device_recalls`, `gudid`, `maude`, `clinicaltrials`, `pubmed`.

- **Shared connector behaviour:** every connector uses retry with backoff and a TTL HTTP cache, and is Kenvue-guarded.
- **Isolation and tracking:** a failure in one source never affects another. Each run records `last_success`, `items` and `status` (`GET /api/sources/status`).
- **Label sync:** label syncs diff each section against the previous version and create `LabelChange` nodes, so you can see which assets need re-review.
- **FAERS signals:** FAERS computes PRR/ROR disproportionality. `SafetySignal` nodes are created only when PRR ≥ 2, χ² ≥ 4, n ≥ 3 and the ROR 95% CI lower bound is above 1 (Evans criteria).
- **Two-phase expansion:** `POST /api/expand` resolves or creates the product (phase 1), then fans out to every applicable source as a background job (`GET /api/expand/{job_id}`).

## Evaluation

```bash
cd backend
python -m app.evals.run_eval --out ../docs/EVAL.md
```

The harness runs 40 golden queries. GraphRAG scores recall@5 0.99 and MRR 0.975, against MRR 0.68 for BM25, 0.57 for dense and 0.65 for hybrid.
Routing accuracy is 0.975, and groundedness and answer-entity hit are both 1.0. See [docs/EVAL.md](docs/EVAL.md). CI fails if GraphRAG drops below the regression gate.

## MCP server (collaboration channel)

The MCP server lets other J&J teams' assistants (Copilot, Claude Desktop, internal agents) query the graph:

```json
{ "mcpServers": { "jnj-graphrag-nexus": {
    "command": "backend/.venv/Scripts/python", "args": ["-m", "app.mcp_server"], "cwd": "backend" } } }
```

Tools: `graph_search`, `ego_subgraph`, `procedural_bundle`, `claim_lineage`, `mlr_review`, `agent_query`.

### Live sync notes

- **jnj.com Innovative Medicine:** the server-rendered `ProductSearchPromo` cards are parsed (brand, generic name, therapeutic area, PI PDF link). Products that already exist in the curated graph are only *enriched* with provenance (`prescribing_info_url`, `jnj_source_url`). Their curated name, franchise and edges are never overwritten.
- **NIH DailyMed:** resolves the latest SPL set id, downloads the label PDF, extracts its sections and links it as `SUPPORTED_BY_EVIDENCE`.
- **TLS:** HTTPS uses the OS trust store via `truststore`, so it works behind corporate TLS inspection.
- **jnjmedtech.com:** the site bot-blocks automated clients (HTTP 403). The sync reports this in `messages` and continues. Use URL, text or PDF ingestion for MedTech devices.

## REST API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Store backend, LLM mode, auth mode, node/edge/SKU/franchise counts |
| GET | `/api/me` | Resolved principal (name, role) |
| GET | `/api/graph?division=&node_type=A,B&search=` | Filtered graph for visualisation |
| GET | `/api/graph/ego/{id}?hops=2` | Ego subgraph + serialized paths + claim lineage |
| GET | `/api/procedures` | Procedure nodes |
| POST | `/api/bundle/recommend` | `{procedure_id, annual_procedure_volume, include_post_op_consumables}` → 4-tier BOM + ROI |
| POST | `/api/bundle/export.docx` | Same body → value-analysis-committee proposal (DOCX) |
| POST | `/api/agent/query` | `{query, top_k, max_hops}` → routed agent, trace, markdown, passages, subgraph, citations, confidence, risk level, guardrails, `query_id` |
| POST | `/api/feedback` | `{query_id, rating: 1\|-1, comment}` |
| POST | `/api/ingest/sync` | JSON `{mode: live\|dailymed\|url\|text\|<evidence source>\|expand}` or multipart PDF upload (`mode=pdf`) |
| GET | `/api/sources/status` | Per-source freshness (cadence, last success, items, due) |
| POST | `/api/sources/sync/{source}` · `/api/sources/refresh` | Sync one source for a product · refresh all due sources |
| POST/GET | `/api/expand` · `/api/expand/{job_id}` | Two-phase portfolio expansion job |
| POST | `/api/mlr/review` | `{text, title, use_llm}` → claims, findings, summary |
| GET | `/api/mlr/reviews` · `/api/mlr/{id}` · `/api/mlr/library` | Review history, detail (with decisions), approved claims |
| POST | `/api/mlr/{id}/decisions` · `/api/mlr/{id}/claims/{cid}/approve` | Reviewer decisions · approve into library (mlr/medical) |
| GET | `/api/mlr/{id}/export.docx` | Annotated review for the MLR committee |
| GET | `/api/metrics/usage` | Queries, latency, confidence, satisfaction, tool calls, LLM tokens/cost, MLR activity |
| GET | `/api/audit` · `/api/audit/verify` | Append-only audit log (admin/mlr) · hash-chain integrity check |
| POST | `/api/eval/run` | Run the golden-set evaluation |
| GET | `/api/prompts` | Versioned prompt templates |
| POST/GET | `/api/admin/keys` | Mint / list API keys (admin) |
| POST | `/api/admin/reseed` | Rebuild the graph from the golden dataset (admin/medical) |

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

`cd backend; pytest tests -q` runs 57 offline tests. CI (`.github/workflows/ci.yml`) runs them, publishes the eval
report, and builds the frontend. `tests/test_improvements.py` covers:

- retry/cache
- audit hash-chain tamper evidence
- guardrails
- PRR math
- mocked openFDA label sync and change detection
- connector failure isolation
- entity resolution
- MLR checks/API/DOCX
- role gates
- feedback/usage
- MCP
- the eval regression gate

`tests/test_end_to_end.py` covers:

- Kenvue exclusion
- Seed integrity
- 2-hop traversal (`PROC_AFIB_ABLATION` → `MT_CARTOSEG_CT` via `MT_CARTO_3_V8`, and → `MT_BIOPATCH_CHG`)
- Bundle ROI math
- Hybrid retrieval
- Supervisor routing to all three agents
- Scraper/PDF parsers
- All FastAPI endpoints

It uses FastAPI `TestClient` and runs fully offline.

## Further reading

- [PITCH.md](PITCH.md): business case, ROI model and pilot ask
- [IMPROVEMENTS.md](IMPROVEMENTS.md): prioritised roadmap benchmarked against 9 reference pharma/biomed GraphRAG and MLR repos
