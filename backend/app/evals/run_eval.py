"""Offline retrieval / routing / answer evaluation over the seed knowledge graph.

Run:  python -m app.evals.run_eval [--k 5] [--no-answers] [--out ../docs/EVAL.md]
Compares BM25-only, dense-only, hybrid (RRF) and full GraphRAG (entity pinning + rerank + graph) retrieval.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from app.agents.supervisor import AGENT_LABELS, get_supervisor, route_query
from app.models.schemas import AgentQueryRequest
from app.rag.hybrid_retriever import get_retriever

GOLDEN_PATH = Path(__file__).with_name("golden.json")
METHODS = ("bm25", "dense", "hybrid", "graphrag")


def load_golden(path: Path = GOLDEN_PATH) -> List[Dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def _dedupe(ids: Sequence[str]) -> List[str]:
    return list(dict.fromkeys(ids))


def rankings(retriever, query: str) -> Dict[str, Any]:
    to_node = lambda pairs: _dedupe(retriever.doc_node.get(d, d) for d, _ in pairs)
    retriever._ensure_index()
    bm25, dense = retriever.bm25_rank(query), retriever.dense_rank(query)
    res = retriever.retrieve(query, top_k=5)
    graph = _dedupe([retriever.doc_node.get(m, m) for m in res["entity_mentions"]]
                    + [n for c in res["reranked_passages"] if c["type"] == "passage" for n in c["node_ids"][:1]]
                    + res["seeds"] + to_node(retriever.rrf([bm25, dense])))
    return {"bm25": to_node(bm25), "dense": to_node(dense), "hybrid": to_node(retriever.rrf([bm25, dense])), "graphrag": graph,
            "retrieval": res}


def recall_at(ranked: Sequence[str], expected: Sequence[str], k: int) -> float:
    return len(set(ranked[:k]) & set(expected)) / len(expected) if expected else 0.0


def reciprocal_rank(ranked: Sequence[str], expected: Sequence[str]) -> float:
    return next((1.0 / (i + 1) for i, n in enumerate(ranked) if n in expected), 0.0)


def citation_precision(store, passages: List[Dict[str, Any]], expected: Sequence[str]) -> float:
    """Share of returned passages that sit on, or one hop from, an expected node."""
    allowed = set(expected)
    for nid in expected:
        if store.has_node(nid):
            allowed |= set(store.graph.successors(nid)) | set(store.graph.predecessors(nid))
    if not passages:
        return 0.0
    return sum(1 for c in passages if set(c["node_ids"]) & allowed) / len(passages)


def run_eval(store, k: int = 5, answers: bool = True, golden: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    t0 = time.perf_counter()
    golden = golden or load_golden()
    retriever = get_retriever(store)
    per_method = {m: {"recall": 0.0, "mrr": 0.0} for m in METHODS}
    routing_hits, cite_prec, grounded, answer_hit = 0, 0.0, 0, 0
    failures: List[Dict[str, Any]] = []
    sup = get_supervisor(store) if answers else None
    for item in golden:
        exp = item["expected_nodes"]
        r = rankings(retriever, item["query"])
        for m in METHODS:
            per_method[m]["recall"] += recall_at(r[m], exp, k)
            per_method[m]["mrr"] += reciprocal_rank(r[m], exp)
        agent, _, _ = route_query(item["query"], r["retrieval"], store)
        routed = AGENT_LABELS[agent]
        routing_hits += routed == item["expected_agent"]
        cite_prec += citation_precision(store, r["retrieval"]["reranked_passages"], exp)
        miss = recall_at(r["graphrag"], exp, k) < 1.0
        if answers and sup is not None:
            resp = sup.run(AgentQueryRequest(query=item["query"]), role="medical", actor="eval")
            grounded += bool(resp.citations) or bool(resp.reranked_passages)
            names = [store.graph.nodes[n]["name"].split(" (")[0].lower() for n in exp if store.has_node(n)]
            answer_hit += any(nm in resp.answer_markdown.lower() for nm in names)
        if miss or routed != item["expected_agent"]:
            failures.append({"id": item["id"], "query": item["query"], "expected": exp, "got_top": r["graphrag"][:k],
                             "expected_agent": item["expected_agent"], "routed": routed})
    n = len(golden)
    summary = {
        "n": n, "k": k,
        "methods": {m: {f"recall@{k}": round(v["recall"] / n, 4), "mrr": round(v["mrr"] / n, 4)} for m, v in per_method.items()},
        "routing_accuracy": round(routing_hits / n, 4),
        "citation_precision": round(cite_prec / n, 4),
        "failures": failures,
        "dense_method": retriever.dense_method, "reranker": retriever.rerank_method,
    }
    if answers:
        summary["groundedness"] = round(grounded / n, 4)
        summary["answer_entity_hit"] = round(answer_hit / n, 4)
    summary["elapsed_s"] = round(time.perf_counter() - t0, 2)
    return summary


def to_markdown(s: Dict[str, Any]) -> str:
    k = s["k"]
    lines = ["# Retrieval & Answer Evaluation", "",
             f"Golden set: **{s['n']} queries** over the seed graph (`backend/app/evals/golden.json`). "
             f"Dense encoder: `{s['dense_method']}`; reranker: `{s['reranker']}`.", "",
             "Regenerate with `python -m app.evals.run_eval --out ../docs/EVAL.md` (from `backend/`).", "",
             f"| Method | Recall@{k} | MRR |", "|---|---|---|"]
    for m, v in s["methods"].items():
        lines.append(f"| {m} | {v[f'recall@{k}']:.3f} | {v['mrr']:.3f} |")
    lines += ["", "| Metric | Value |", "|---|---|", f"| Supervisor routing accuracy | {s['routing_accuracy']:.3f} |",
              f"| Citation precision (passages on/adjacent to expected nodes) | {s['citation_precision']:.3f} |"]
    if "groundedness" in s:
        lines += [f"| Groundedness (answers with citations) | {s['groundedness']:.3f} |",
                  f"| Answer mentions expected entity | {s['answer_entity_hit']:.3f} |"]
    if s["failures"]:
        lines += ["", "## Misses", "", "| ID | Query | Expected | GraphRAG top-k | Routed (expected) |", "|---|---|---|---|---|"]
        for f in s["failures"]:
            lines.append(f"| {f['id']} | {f['query']} | {', '.join(f['expected'])} | {', '.join(f['got_top'])} | "
                         f"{f['routed']} ({f['expected_agent']}) |")
    return "\n".join(lines) + "\n"


def main() -> None:  # pragma: no cover - CLI
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--no-answers", action="store_true")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    from app.graph.graph_store import get_graph_store

    s = run_eval(get_graph_store(), k=args.k, answers=not args.no_answers)
    print(json.dumps({k: v for k, v in s.items() if k != "failures"}, indent=1))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(to_markdown(s), encoding="utf-8")
        print(f"wrote {args.out}")


if __name__ == "__main__":  # pragma: no cover
    main()
