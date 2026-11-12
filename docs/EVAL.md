# Retrieval & Answer Evaluation

Golden set: **40 queries** over the seed graph (`backend/app/evals/golden.json`). Dense encoder: `tfidf-svd-dense-projection`; reranker: `calibrated-lexical-graph-overlap`.

Regenerate with `python -m app.evals.run_eval --out ../docs/EVAL.md` (from `backend/`).

| Method | Recall@5 | MRR |
|---|---|---|
| bm25 | 0.963 | 0.678 |
| dense | 0.900 | 0.570 |
| hybrid | 0.912 | 0.645 |
| graphrag | 0.988 | 0.975 |

| Metric | Value |
|---|---|
| Supervisor routing accuracy | 0.975 |
| Citation precision (passages on/adjacent to expected nodes) | 0.745 |
| Groundedness (answers with citations) | 1.000 |
| Answer mentions expected entity | 1.000 |

## Misses

| ID | Query | Expected | GraphRAG top-k | Routed (expected) |
|---|---|---|---|---|
| Q03 | Cross-sell Ethicon consumables after robotic knee arthroplasty | PROC_TKA_ROBOTIC, MT_VELYS_ROBOT | MT_VELYS_ROBOT, MT_MONOCRYL_PLUS, MT_BLAKE_DRAIN, DOC_DEPUY_VELYS_TECH, COND_KNEE_OA | medtech_bundler (medtech_bundler) |
| Q37 | Regulatory evidence for Shockwave Javelin IFU | MT_SHOCKWAVE_JAVELIN, DOC_SHOCKWAVE_JAVELIN_IFU | MT_SHOCKWAVE_IVL_GENERATOR, MT_SHOCKWAVE_JAVELIN, DOC_SHOCKWAVE_JAVELIN_IFU, PROC_CALCIFIED_PCI, DOC_WINDCHILL_502735931 | medtech_bundler (regulatory_auditor) |
