# Improvement Roadmap: Lessons from 9 Reference Repositories

This document compares J&J GraphRAG Nexus against nine related pharma/biomed GraphRAG and MLR codebases.
The comparison uses the AST-symbol and dependency index in `similar_repo/` (21,965 symbols, 904 files). Each
recommendation lists:
- the **reference pattern** (repo, file, symbol)
- **our current gap** (file in this repo)
- a **concrete design** for our stack
- **effort** and **pitch value**

> **Licensing:** none of the indexed reference repos contains a LICENSE file in the index. Treat them as
> *design references only*. Re-implement the patterns; do not copy their code.

---

## 0. Benchmark at a glance

| Repo | What it does well | Relevance to us |
|---|---|---|
| **OpenMLR** (Next.js/TS) | Full MLR review pipeline: claim extraction, 10 specialised checks, findings with severity, reviewer decisions, claims library, FDA OPDP precedent | ★★★★★ upgrades our Claim Auditor into a real MLR pre-review product |
| **ClinicalDocIntelligence** | Input/output guardrails (PHI, prompt injection), section-aware label chunking, safety-section boosting, MMR, evaluator, MCP server, model router with cost tracking | ★★★★★ |
| **BiomedEvidenceMCP** | Production connectors (openFDA label/event/enforcement/drugsfda, ClinicalTrials.gov, PubMed), HTTP retry with Retry-After, TTL cache, incremental refresh with watermarks, per-call metering, API-key gate, retrieval eval with recall@k (44 test files) | ★★★★★ |
| **PharmaGraphRAG** | RAGAS evaluation (faithfulness, context precision/recall), agent tool-selection F1, Langfuse observability with no-op fallback, longest-first + fuzzy entity extraction, FAERS graph | ★★★★☆ |
| **TruPharma** | FAERS disproportionality signals (PRR/ROR), RxNorm name resolution, query analyser with regex fallback, KG-enriched embeddings, two-phase dynamic graph expansion, interaction logging | ★★★★☆ |
| **BioGraphRAG** | Prize-Collecting Steiner Tree subgraph pruning (G-Retriever style) | ★★★☆☆ |
| **DruGraph** (React + FastAPI) | ONNX MiniLM embeddings (no torch, ~800 MB RAM saved), interaction/compatibility checker, alternatives view | ★★★☆☆ |
| **CGX** | Baseline comparison (vanilla RAG vs GraphRAG), three-layer graph linking | ★★☆☆☆ (heavy; borrow the eval idea only) |
| **Bridge-MedDevKG** | Medical-device KG, hard-negative export for cross-encoder training | ★★☆☆☆ (later: fine-tuning) |

**Where we are already ahead:**
- typed cross-sector IM × MedTech graph
- procedural bundle economics
- Kenvue guardrail
- a single UI that combines graph, bundler and co-pilot
- fully offline operation
- live jnj.com reconciliation

None of the reference repos has a commercial cross-sell use case.

**Our complexity hotspots** (from the index; candidates to refactor while adding features):

| Symbol | Cyclomatic complexity |
|---|---|
| `ForceGraphCanvas` | 130 |
| `GraphExplorer` | 64 |
| `IngestionModal` | 51 |
| `main.ingest_sync` | 50 |
| `HybridGraphRetriever.retrieve` | 33 |

---

## Tier 1: highest value for the manager pitch (do first)

### 1. Turn the Claim Auditor into an MLR pre-review pipeline

- **Reference:** OpenMLR `src/lib/pipeline/*`
  - `extractClaims`, `segmentAsset`/`extractAcrossSegments` (12k-char segmenting)
  - `verifyClaim`
  - `checkFairBalance`, `checkSafetyOmission`, `checkOffLabel`, `checkComparative`, `checkMarketClaims` (`MARKET_RE`), `checkIp` (`NOVELTY_RE`), `checkCitationQuality` (`STALE_YEARS = 10`, preprint hints), `checkAdverseEvents`
  - `assembleFindings`, `verdictSeverity`
  - schema tables `finding_decisions` (append-only) and `claims_library`
- **Our gap:** `regulatory_auditor_agent` in [supervisor.py](backend/app/agents/supervisor.py) only traces claims *already stored on nodes*. It cannot review a piece of promotional copy.
- **Design:**
  - New `backend/app/mlr/` package and a `POST /api/mlr/review` endpoint that accepts text or a PDF asset.
  - Segment the asset and extract claims, typed as `efficacy | safety | comparative | mechanism | indication | dosing | economic | epidemiology`. Use regex/heuristics offline and an LLM when one is configured.
  - Verdicts: `supported | partial | unsupported | contradicted | no_evidence`, each with a confidence. Following OpenMLR, `no_evidence` is a *retrieval gap*, not a critical finding.
  - **Graph-native checks** that no reference repo can do deterministically:
    - **Off-label:** the claimed condition is not reachable via `INDICATED_FOR` from the product.
    - **Safety omission:** the product has a `HAS_BOXED_WARNING` edge, but the asset text does not mention that warning.
    - **Cross-product claims:** "use with X" without a `COMPATIBLE_WITH`/`SYNERGISTIC_PATHWAY_WITH` edge.
  - Severity levels `critical | warning | unverified | info`. Show severity by **shape and colour** (OpenMLR `SEV_GLYPH`) for accessibility.
  - Reviewer decisions `accepted | rejected | revision`, stored append-only with the reviewer and rationale.
  - **Claims library:** reuse prior verdicts by exact normalised match, then semantic match (cosine ≥ 0.85).
  - **Enforcement precedent:** index public-domain FDA OPDP untitled/warning letters and show the nearest precedent for each finding.
- **Frontend:** a new "MLR Pre-Review" tab:
  - asset text with inline highlights anchored to claims (OpenMLR `fuzzyFind`/`anchorClaims`)
  - a findings list with an accept/reject/revise action for each finding
  - DOCX/PDF export
- **Effort:** 2–3 weeks.
- **Pitch value:** very high. It is a directly measurable MLR time saving (PITCH §4a) and turns a demo into a workflow.

### 2. Evaluation harness with a GraphRAG vs. baseline scorecard

- **Reference:**
  - PharmaGraphRAG `evaluation/` (`EvalDataset`, `to_ragas_dataset`, `score_sample`, `evaluate_tool_selection` precision/recall/F1)
  - BiomedEvidenceMCP `scripts/eval_retrieval.py` (`CUTOFFS = (1, 3, 5, 10)`, Markdown report with preserved hand-written analysis)
  - ClinicalDocIntelligence `RAGEvaluator` (offline keyword mode plus an LLM-as-judge mode)
  - CGX `compare_baselines.py`
- **Our gap:** we have 36 functional tests but **no quality metrics**.
- **Design:**
  - `backend/evals/golden.json`: 50–100 SME-written items. Each item has a question, expected node ids, expected agent route, expected citations and a reference answer.
  - `backend/evals/run_eval.py` computes:
    - recall@1/3/5/10 and MRR
    - routing accuracy
    - citation precision
    - groundedness (offline token-overlap; RAGAS faithfulness when an LLM is configured)
    - claim-audit precision/recall
  - **Baselines:** BM25-only, dense-only and full GraphRAG, run on the same set. This produces the "GraphRAG is +X pts recall" headline.
  - Write `docs/EVAL.md` and fail CI on regression.
- **Effort:** 1 week (plus SME time to write the golden set).
- **Pitch value:** very high. It supplies the KPI numbers in PITCH §8 ("managers approve numbers").

### 3. Guardrails: PHI, prompt injection, output checks, confidence

- **Reference:** ClinicalDocIntelligence `src/guardrails/validators.py`
  - `InputGuardrails`: `PHI_PATTERNS`, `INJECTION_PATTERNS`, sanitising
  - `OutputGuardrails`: citation presence, `UNSUPPORTED_CLAIM_PATTERNS` ("100% effective", "no side effects"), confidence threshold, `CLINICAL_DISCLAIMER`
  - `RiskLevel` (`low | medium | high | blocked`)
  - `MultiAgentCoordinator._request_human_approval`
  - confidence from retrieval quality: `RAGChain._estimate_confidence`, TruPharma `_confidence`
- **Our gap:** the Kenvue filter is the only guardrail. **Ingested web/PDF text is untrusted** (indirect prompt injection) and is currently passed to the optional LLM polish step.
- **Design:**
  - A `backend/app/guardrails.py` module, applied to `/api/agent/query` input and to every ingestion path.
  - Responses gain `confidence` and `risk_level` fields. Safety-critical answers (boxed warning or contraindication in context) get a "requires medical review" banner.
  - Add a standard disclaimer to the answer.
- **Effort:** 3–4 days.
- **Pitch value:** high. It answers the "compliance will block it" objection.

### 4. Sanctioned regulatory data connectors (replacing scraping)

- **Reference:**
  - BiomedEvidenceMCP `servers/openfda_shared/_base.py` (`OpenFDAConnectorBase` with `skip` paging, the 25k ceiling and `_payload_or_none` for HTML-on-200 responses), plus connectors for openFDA label/event/enforcement/drugsfda, ClinicalTrials.gov (`CTGovConnector`) and PubMed (`PubMedConnector`)
  - TruPharma `kg/builders/faers_edges.py` and `label_edges.py`
- **Our gap:** we use jnj.com scraping (fragile; jnjmedtech.com returns 403) and DailyMed only.
- **Design:** a `backend/app/ingestion/connectors/` package with one class per source, sharing one base:
  - **MedTech:** openFDA `device/udi` (GUDID), `device/event` (MAUDE), `device/recall`, `device/510k`/`pma`. **This fixes the jnjmedtech.com 403 with official data.**
  - **Pharma:** openFDA `drug/label` and `drug/event` (FAERS), plus `drug/enforcement`.
  - **Evidence:** ClinicalTrials.gov v2 and PubMed E-utilities create `ClinicalTrial` and `Publication` nodes linked by `SUPPORTED_BY_EVIDENCE`.
- **Effort:** 1–2 weeks.
- **Pitch value:** high. It removes the scraping risk and adds an evidence layer.

---

## Tier 2: robustness and quality (pilot phase)

### 5. Ingestion reliability: retry, cache and incremental refresh

- **Reference:** BiomedEvidenceMCP
  - `core/http_retry.py`: retry 429/5xx, honour `Retry-After` (capped at 60 s), delays of 2/5/10 s
  - `_redact_url` to strip API keys from logs
  - `core/cache.py` `TTLCache`
  - `core/refresh.py`: `source_state` with `watermark`, cadence (`daily`/`weekly`), `--due`, per-source failure isolation
  - `corpus_status` tool
- **Our gap:** `JnJIngestionScraper._get` makes a single attempt with no caching, and there is no freshness tracking.
- **Design:**
  - Add a shared `http_get_with_retry()` and an in-process TTL cache.
  - Add a `source_state` table (SQLite, or JSON alongside the graph).
  - Add `/api/sources/status`. Show data freshness ("DailyMed synced 2 d ago") in the MetricsRibbon.
  - Run a scheduled refresh (APScheduler locally; Azure Functions timer in the cloud).
- **Effort:** 3–4 days.

### 6. Label-change monitoring

- **Reference:** BiomedEvidenceMCP `refresh_source` (watermark diffing).
- **Design:**
  - Persist label sections with a version or `effective_time`. Diff sections on refresh.
  - When `BOXED WARNING`, `INDICATIONS` or `CONTRAINDICATIONS` changes, create a `LabelChange` node and list the affected claims and claims-library entries.
- **Effort:** 3–4 days.
- **Pitch value:** high. MLR teams track label changes manually today.

### 7. Retrieval upgrades

| Upgrade | Reference | Change in [hybrid_retriever.py](backend/app/rag/hybrid_retriever.py) |
|---|---|---|
| Section-aware label chunks | ClinicalDocIntelligence `SectionAwareChunker` (`NEVER_SPLIT = {"boxed_warning", "contraindications"}`) | Index label *sections* as evidence passages, not just node text |
| Safety-section boost | `HybridRetriever._boost_by_priority` | Boxed warnings and contraindications surface first for safety queries |
| MMR diversity | `HybridRetriever._mmr_diversify` | Avoid top-k results coming from one product |
| Entity resolution | PharmaGraphRAG `extract_entities` (longest-first exact match, then fuzzy); TruPharma `rxnorm.resolve_drug_name` | Resolve brand, generic and misspellings to node ids. **Also hardens the Kenvue filter** against brand variants |
| Query analyser | TruPharma `analyze_query` (LLM with `_regex_fallback`) and `_drug_is_known` out-of-scope gate | Replace keyword weights in `route_query`; refuse out-of-scope questions politely |
| Subgraph pruning | BioGraphRAG `prune_subgraph` / `_node_prize` / `_edge_weight` (PCST) | A compact, relevant subgraph gives better context and a cleaner spotlight |
| KG-enriched embeddings | TruPharma `enrich_chunk` | Prepend franchise, indication and procedure context to passages before embedding |
| Lightweight semantic vectors | DruGraph `ONNXEmbeddings` (MiniLM via onnxruntime) | Real semantic embeddings offline without torch; replaces the TF-IDF+SVD fallback |

- **Effort:** 1–2 weeks in total, each change measured with the eval harness (#2).

### 8. Pharmacovigilance signals

- **Reference:** TruPharma `signal_detector.FaersClient.get_contingency_table` and `detect_signals` (PRR/ROR); OpenMLR `checkAdverseEvents`.
- **Design:**
  - Compute PRR/ROR for each J&J product × reaction from FAERS counts and create `SafetySignal` nodes.
  - The MLR check then flags safety/tolerability claims that are inconsistent with signals.
  - The explorer can show a safety overlay.
- **Effort:** 1 week.

### 9. LLM provider routing and cost tracking

- **Reference:** ClinicalDocIntelligence `ModelRouter` (fallback order, `TokenTracker`, `PRICING`) and `PromptManager` (YAML-versioned prompts).
- **Our gap:** `_llm_polish` in [supervisor.py](backend/app/agents/supervisor.py) tries OpenAI then Gemini, with no cost tracking or prompt versioning.
- **Design:**
  - Provider order: Azure OpenAI, then a fallback, then the deterministic generator.
  - Track tokens and cost per request.
  - Keep prompts in `backend/app/prompts/*.yaml` with versions. MLR auditors can then see exactly which prompt produced an answer.
- **Effort:** 3 days.

---

## Tier 3: enterprise readiness (scale decision)

### 10. Observability, metering and audit trail

- **Reference:**
  - PharmaGraphRAG `observability.py` (`observe_fn` decorator that becomes a no-op when unconfigured)
  - BiomedEvidenceMCP `core/metering.py` (`metered_call`, `tool_calls` table)
  - OpenMLR `audit_entries`
  - TruPharma `log_row`
- **Design:**
  - Use an OpenTelemetry/App Insights decorator on each LangGraph node. `execution_trace` already exists, so persist it.
  - Add a `query_log` table recording user, route, latency, confidence and feedback.
  - Add an append-only audit log for ingestion and MLR decisions.
  - Add a usage dashboard. It **directly evidences the ROI/adoption KPIs** in the pitch.

### 11. Access control

- **Reference:** BiomedEvidenceMCP `mcp_platform/gate.py` (sha256-hashed API keys, tiers, monthly limits, an exempt status tool).
- **Design:**
  - Entra ID SSO for users.
  - Hashed service keys for machine clients (MCP).
  - Role views for commercial, medical and MLR users. This keeps the commercial/medical firewall: commercial users should not see unsolicited off-label content.

### 12. MCP server: the "collaboration" channel

- **Reference:** ClinicalDocIntelligence `src/agents/mcp_server.py` (JSON-RPC over stdio: `tools/list`, `tools/call`); BiomedEvidenceMCP (FastMCP servers per source).
- **Design:** expose `graph_search`, `ego_subgraph`, `procedural_bundle`, `claim_lineage` and `mlr_review` as MCP tools.
- **Why it matters:** Copilot, Teams agents and partner teams can consume J&J's governed knowledge graph without building UIs. This is the concrete mechanism behind "J&J and its collaborators".

### 13. Two-phase dynamic graph expansion

- **Reference:** TruPharma `dynamic_builder.expand_drug_phase1` / `expand_drug_phase2` / `get_build_status`.
- **Design:**
  - When a user searches for an unknown J&J product, phase 1 adds the identity node synchronously (RxNorm/GUDID).
  - Phase 2 (FAERS, label, trials) runs in the background, and the UI polls a status endpoint.

### 14. Reports and exports

- **Reference:** OpenMLR `docx-report.ts`; TruPharma `generate_walkthrough_pdf.py`.
- **Design:**
  - Bundle proposal export (PDF/DOCX/PPTX) for account teams.
  - MLR pre-review package export.

### 15. Frontend refactor and tests

- Split `ForceGraphCanvas` (cyclomatic complexity 130) into `useForceSimulation`, `drawGraph` and `useCanvasInteractions`.
- Split `GraphExplorer`, `IngestionModal` and `ingest_sync` (one handler per ingestion mode).
- Add Vitest unit tests and Playwright smoke tests. The repo currently has 1 test file versus 44 in BiomedEvidenceMCP.
- Adopt the UX patterns from OpenMLR and DruGraph:
  - staged run-progress
  - toasts
  - history/library views
  - a compatibility checker (DruGraph `check_drug_list` becomes "check this product set for pathway and compatibility conflicts")

---

## What NOT to adopt (and why)

| Pattern | Reason |
|---|---|
| CGX CAMEL agent "societies" and role-playing | Heavy and non-deterministic. Our LangGraph supervisor is simpler and auditable. |
| BioGraphRAG GNN/PyG reranker | Its own `rerank_candidates` is a placeholder. Torch weight is not justified at a graph of about 100–10k nodes. |
| CGX UMLS three-layer import | UMLS requires a licence. Use MeSH/SNOMED only with legal approval. |
| AWS Neptune / Bedrock paths (BioGraphRAG, ClinicalDocIntelligence) | J&J target cloud is Azure. Keep Neo4j/Cosmos and Azure OpenAI. |
| OpenMLR Valyu paid search and anonymous trial metering | Third-party data egress; not needed internally. |
| TruPharma opioid-specific modules | Out of domain. Reuse only the FAERS signal maths. |

---

## Suggested sequencing

| Sprint (2 wk) | Deliverables | Pitch KPI unlocked |
|---|---|---|
| 1 | #2 eval harness and golden set, #3 guardrails, #5 retry/cache | Groundedness and citation accuracy numbers; compliance story |
| 2 | #1 MLR pre-review (backend and graph-native checks) | MLR pre-screen precision |
| 3 | #1 MLR UI, #4 openFDA/GUDID/CT.gov connectors | Time-to-review; MedTech data without scraping |
| 4 | #7 retrieval upgrades (measured by #2), #6 label-change alerts | Recall improvement vs baseline |
| 5 | #10 observability/audit, #11 SSO, #12 MCP server | Adoption metrics; enterprise readiness |
| 6 | #8 FAERS signals, #14 exports, #15 refactor and tests | Pilot exit review |

Pick **#2, #3 and #1** before the approval meeting if time allows. Together they convert the demo into
measurable, compliant workflow value.
