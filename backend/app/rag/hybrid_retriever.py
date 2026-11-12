"""Hybrid GraphRAG retriever: BM25Okapi + dense vectors + RRF + 2-hop graph expansion + cross-encoder rerank."""
from __future__ import annotations

import logging
import math
import re
import threading
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from rank_bm25 import BM25Okapi
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer

from app.config import get_settings
from app.graph.graph_store import HUB_TYPES, NODE_COLORS
from app.models.schemas import NodeType

if TYPE_CHECKING:  # pragma: no cover
    from app.graph.graph_store import GraphStore

logger = logging.getLogger(__name__)

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "do", "does", "for", "from", "how", "in", "include", "including",
    "is", "it", "of", "on", "or", "the", "their", "them", "this", "to", "what", "which", "with", "work", "j", "jnj",
    "complete", "build", "end", "together", "across", "all", "any", "can", "into", "our", "that", "these", "those",
}
RRF_K = 60
PASSAGE_TYPES = {
    NodeType.Product.value, NodeType.SoftwareModule.value, NodeType.Procedure.value, NodeType.EvidenceDocument.value,
    NodeType.BoxedWarning.value, NodeType.ClinicalCondition.value, NodeType.Anatomy.value, NodeType.HardwareCoupling.value,
}
ENTITY_TYPES = {NodeType.Product.value, NodeType.SoftwareModule.value, NodeType.Procedure.value}


def tokenize(text: str) -> List[str]:
    return [t for t in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", text.lower()) if t not in STOPWORDS and len(t) > 1]


def _try_sentence_transformers():
    if not get_settings().use_transformer_models:
        return None, None
    try:  # Optional heavy dependency
        from sentence_transformers import CrossEncoder, SentenceTransformer  # type: ignore

        return SentenceTransformer("all-MiniLM-L6-v2"), CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    except Exception as exc:  # pragma: no cover - depends on environment
        logger.info("sentence-transformers unavailable (%s); using TF-IDF/SVD + lexical-graph reranker", exc)
        return None, None


class HybridGraphRetriever:
    def __init__(self, store: "GraphStore", use_transformers: Optional[bool] = None):
        self.store = store
        self._lock = threading.RLock()
        self._version: Tuple[int, int] = (-1, -1)
        self._bm25: BM25Okapi
        self._bi_encoder = None
        self._cross_encoder = None
        if use_transformers is None or use_transformers:
            self._bi_encoder, self._cross_encoder = _try_sentence_transformers()
        self.dense_method = "sentence-transformers/all-MiniLM-L6-v2" if self._bi_encoder else "tfidf-svd-dense-projection"
        self.rerank_method = "cross-encoder/ms-marco-MiniLM-L-6-v2" if self._cross_encoder else "calibrated-lexical-graph-overlap"
        self.doc_ids: List[str] = []
        self.doc_texts: List[str] = []

    # ------------------------------------------------------------------ corpus
    def passage_text(self, node_id: str) -> str:
        d = self.store.graph.nodes[node_id]
        props = d.get("properties", {})
        parts = [d["name"], f"[{d['label']}]"]
        if d.get("division"):
            parts.append(d["division"])
        if d.get("franchise"):
            parts.append(f"Franchise: {d['franchise']}")
        for key in ("sku", "category", "generic_name", "mechanism", "indication", "clinical_claim", "modality", "trial_data",
                    "boxed_warning", "warning_text", "contraindication", "excerpt", "description", "windchill_id", "doc_type"):
            if props.get(key):
                parts.append(f"{key.replace('_', ' ')}: {props[key]}")
        rels = []
        for s, t, ed in self.store.graph.out_edges(node_id, data=True):
            rels.append(f"{ed['relation'].replace('_', ' ').lower()} {self.store.graph.nodes[t]['name']}")
        for s, t, ed in self.store.graph.in_edges(node_id, data=True):
            if self.store.graph.nodes[s]["label"] not in HUB_TYPES:
                rels.append(f"{self.store.graph.nodes[s]['name']} {ed['relation'].replace('_', ' ').lower()}")
        if rels:
            parts.append("Relations: " + "; ".join(rels[:14]))
        return ". ".join(parts)

    def _ensure_index(self) -> None:
        version = (id(self.store), self.store.revision)
        if version == self._version:
            return
        with self._lock:
            if version == self._version:
                return
            ids = [n for n, d in self.store.graph.nodes(data=True) if d["label"] in PASSAGE_TYPES]
            texts = [self.passage_text(n) for n in ids]
            self.doc_ids, self.doc_texts = ids, texts
            self._bm25 = BM25Okapi([tokenize(t) or ["empty"] for t in texts])
            if self._bi_encoder is not None:
                self._dense = np.asarray(self._bi_encoder.encode(texts, normalize_embeddings=True))
            else:
                self._tfidf = TfidfVectorizer(tokenizer=tokenize, token_pattern=None, ngram_range=(1, 2), sublinear_tf=True, min_df=1)
                x = self._tfidf.fit_transform(texts)
                n_comp = max(2, min(96, x.shape[0] - 1, x.shape[1] - 1))
                self._svd = TruncatedSVD(n_components=n_comp, random_state=42)
                dense = self._svd.fit_transform(x)
                self._dense = self._normalize(dense)
            self._idf = self._compute_idf(texts)
            self._version = version

    @staticmethod
    def _normalize(m: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(m, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return m / norms

    @staticmethod
    def _compute_idf(texts: Sequence[str]) -> Dict[str, float]:
        df: Dict[str, int] = {}
        for t in texts:
            for tok in set(tokenize(t)):
                df[tok] = df.get(tok, 0) + 1
        n = len(texts)
        return {tok: math.log(1 + n / c) for tok, c in df.items()}

    # ------------------------------------------------------------------ retrieval stages
    def bm25_rank(self, query: str) -> List[Tuple[str, float]]:
        scores = self._bm25.get_scores(tokenize(query) or ["empty"])
        order = np.argsort(-scores)
        return [(self.doc_ids[i], float(scores[i])) for i in order if scores[i] > 0]

    def dense_rank(self, query: str) -> List[Tuple[str, float]]:
        if self._bi_encoder is not None:
            q = np.asarray(self._bi_encoder.encode([query], normalize_embeddings=True))
        else:
            q = self._normalize(self._svd.transform(self._tfidf.transform([query])))
        sims = (self._dense @ q.T).ravel()
        order = np.argsort(-sims)
        return [(self.doc_ids[i], float(sims[i])) for i in order if sims[i] > 0]

    def entity_mentions(self, query: str) -> List[str]:
        """Exact brand / SKU / ID mentions get pinned as graph seeds."""
        q = query.lower()
        qtoks = set(re.findall(r"[a-z0-9]+", q))
        hits: List[Tuple[int, str]] = []
        for nid, d in self.store.graph.nodes(data=True):
            if d["label"] not in ENTITY_TYPES:
                continue
            name = d["name"].lower()
            brand = re.split(r"[\s(/]", name)[0]
            alt = re.findall(r"/\s*([a-z0-9]+)", name)
            sku = str(d.get("properties", {}).get("sku", "")).lower()
            if nid.lower() in q or (sku and sku in q):
                hits.append((0, nid))
            elif name.split(" (")[0] in q:
                hits.append((1, nid))
            elif len(brand) >= 5 and brand in qtoks and brand not in {"carto", "robotic", "catheter", "intravascular"}:
                hits.append((2, nid))
            elif any(a in qtoks for a in alt if len(a) >= 5):
                hits.append((2, nid))
        hits.sort()
        return [nid for _, nid in hits]

    @staticmethod
    def rrf(rankings: Sequence[Sequence[Tuple[str, float]]], k: int = RRF_K) -> List[Tuple[str, float]]:
        fused: Dict[str, float] = {}
        for ranking in rankings:
            for rank, (doc_id, _) in enumerate(ranking, start=1):
                fused[doc_id] = fused.get(doc_id, 0.0) + 1.0 / (k + rank)
        return sorted(fused.items(), key=lambda kv: -kv[1])

    def _lexical_graph_score(self, query_tokens: List[str], text: str, rrf_score: float, hop: int) -> float:
        toks = set(tokenize(text))
        qset = set(query_tokens)
        if not qset:
            return 0.0
        weight_total = sum(self._idf.get(t, 1.0) for t in qset)
        overlap = sum(self._idf.get(t, 1.0) for t in qset if t in toks) / weight_total
        proximity = 1.0 / (1.0 + hop)
        rrf_norm = min(1.0, rrf_score * RRF_K / 2.0)
        logit = 6.0 * overlap + 1.5 * rrf_norm + 1.2 * proximity - 3.0
        return float(1.0 / (1.0 + math.exp(-logit)))

    def rerank(self, query: str, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not candidates:
            return []
        if self._cross_encoder is not None:
            raw = self._cross_encoder.predict([(query, c["text"]) for c in candidates])
            for c, s in zip(candidates, raw):
                c["cross_encoder_score"] = float(1.0 / (1.0 + math.exp(-float(s))))
        else:
            qt = tokenize(query)
            for c in candidates:
                c["cross_encoder_score"] = self._lexical_graph_score(qt, c["text"], c.get("rrf_score", 0.0), c.get("hop", 2))
        return sorted(candidates, key=lambda c: -c["cross_encoder_score"])

    # ------------------------------------------------------------------ main entry
    def retrieve(self, query: str, top_k: int = 5, max_hops: int = 2, seed_count: int = 4) -> Dict[str, Any]:
        t0 = time.perf_counter()
        self._ensure_index()
        bm25 = self.bm25_rank(query)
        dense = self.dense_rank(query)
        fused = self.rrf([bm25, dense])
        fused_scores = dict(fused)
        mentions = self.entity_mentions(query)
        t1 = time.perf_counter()

        seeds: List[str] = []
        for nid in mentions + [d for d, _ in fused]:
            if nid not in seeds and self.store.graph.nodes[nid]["label"] in ENTITY_TYPES | {NodeType.EvidenceDocument.value}:
                seeds.append(nid)
            if len(seeds) >= max(seed_count, min(len(mentions), 6)):
                break

        hop_of: Dict[str, int] = {}
        sub_nodes: Dict[str, Dict[str, Any]] = {}
        sub_links: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        path_candidates: Dict[str, Dict[str, Any]] = {}
        for seed in seeds:
            ego = self.store.ego_subgraph(seed, max_hops)
            for n in ego["nodes"]:
                hop_of[n["id"]] = min(hop_of.get(n["id"], 99), n["hop"])
                sub_nodes.setdefault(n["id"], {k: v for k, v in n.items() if k != "hop"})
            for link in ego["links"]:
                key = (link["source"], link["target"], link["relation"])
                if key in sub_links:
                    continue
                sub_links[key] = link
                src, tgt = link["source"], link["target"]
                if self.store.graph.nodes[src]["label"] in HUB_TYPES or self.store.graph.nodes[tgt]["label"] in HUB_TYPES:
                    continue
                text = f"({self.store.graph.nodes[src]['name']}) -[{link['relation']}]-> ({self.store.graph.nodes[tgt]['name']})"
                props = link.get("properties") or {}
                if props:
                    text += " {" + ", ".join(f"{k}: {v}" for k, v in props.items()) + "}"
                hop = min(hop_of.get(src, 2), hop_of.get(tgt, 2))
                path_candidates[text] = {"id": f"PATH::{src}::{link['relation']}::{tgt}", "type": "graph_path", "text": text,
                                         "node_ids": [src, tgt], "hop": hop, "rrf_score": 0.0}
        t2 = time.perf_counter()

        candidates: List[Dict[str, Any]] = []
        for nid, score in fused[: max(top_k * 4, 20)]:
            candidates.append({"id": nid, "type": "passage", "label": self.store.graph.nodes[nid]["label"],
                               "name": self.store.graph.nodes[nid]["name"], "text": self.doc_texts[self.doc_ids.index(nid)],
                               "hop": hop_of.get(nid, 0 if nid in seeds else 3), "rrf_score": score, "node_ids": [nid]})
        known = {c["id"] for c in candidates}
        for nid in seeds:
            if nid not in known and nid in self.doc_ids:
                candidates.append({"id": nid, "type": "passage", "label": self.store.graph.nodes[nid]["label"],
                                   "name": self.store.graph.nodes[nid]["name"], "text": self.doc_texts[self.doc_ids.index(nid)],
                                   "hop": 0, "rrf_score": fused_scores.get(nid, 1.0 / RRF_K), "node_ids": [nid]})
        candidates += list(path_candidates.values())
        reranked = self.rerank(query, candidates)
        t3 = time.perf_counter()

        top_passages = [c for c in reranked if c["type"] == "passage"][:top_k]
        top_paths = [c for c in reranked if c["type"] == "graph_path"][:top_k]
        merged = sorted(top_passages + top_paths, key=lambda c: -c["cross_encoder_score"])
        for c in merged:
            c["cross_encoder_score"] = round(c["cross_encoder_score"], 4)
            c["rrf_score"] = round(c.get("rrf_score", 0.0), 5)
            c["text"] = c["text"][:700]

        for nid, node in sub_nodes.items():
            node["hop"] = hop_of.get(nid, 2)
            node["is_seed"] = nid in seeds
        return {
            "query": query,
            "seeds": seeds,
            "entity_mentions": mentions,
            "bm25_top": [{"id": d, "score": round(s, 4)} for d, s in bm25[:top_k]],
            "dense_top": [{"id": d, "score": round(s, 4)} for d, s in dense[:top_k]],
            "rrf_top": [{"id": d, "score": round(s, 5)} for d, s in fused[:top_k]],
            "reranked_passages": merged,
            "subgraph": {"nodes": list(sub_nodes.values()), "links": list(sub_links.values())},
            "methods": {"lexical": "BM25Okapi", "dense": self.dense_method, "fusion": f"RRF(k={RRF_K})",
                        "graph": f"{max_hops}-hop ego expansion", "reranker": self.rerank_method},
            "timings_ms": {"hybrid_search": round((t1 - t0) * 1000, 2), "graph_expansion": round((t2 - t1) * 1000, 2),
                           "rerank": round((t3 - t2) * 1000, 2)},
            "colors": NODE_COLORS,
        }


_retriever: Optional[HybridGraphRetriever] = None
_retriever_lock = threading.Lock()


def get_retriever(store: "GraphStore") -> HybridGraphRetriever:
    global _retriever
    with _retriever_lock:
        if _retriever is None or _retriever.store is not store:
            _retriever = HybridGraphRetriever(store)
        return _retriever
