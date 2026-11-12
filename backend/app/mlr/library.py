"""Approved-claims library: reuse prior MLR decisions (exact normalized match, then TF-IDF cosine similarity)."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.core.db import OpsDB, utcnow

SIMILARITY_THRESHOLD = 0.85


def normalize_claim(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9%.\s]", " ", text.lower())).strip()


def add_claim(db: OpsDB, text: str, claim_type: Optional[str], verdict: str, confidence: Optional[float],
              product_ids: List[str], review_id: Optional[str]) -> Dict[str, Any]:
    norm = normalize_claim(text)
    db.execute("INSERT INTO claims_library (normalized, text, claim_type, verdict, confidence, product_ids, review_id, ts) "
               "VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(normalized) DO UPDATE SET uses=uses+1, verdict=excluded.verdict, "
               "review_id=excluded.review_id, ts=excluded.ts",
               (norm, text, claim_type, verdict, confidence, json.dumps(product_ids), review_id, utcnow()))
    return {"normalized": norm, "verdict": verdict}


def lookup(db: OpsDB, texts: List[str]) -> List[Optional[Dict[str, Any]]]:
    """Return the best library match per text (or None)."""
    rows = db.query("SELECT normalized, text, claim_type, verdict, confidence, review_id, ts, uses FROM claims_library")
    if not rows or not texts:
        return [None] * len(texts)
    by_norm = {r["normalized"]: r for r in rows}
    out: List[Optional[Dict[str, Any]]] = []
    norms = [normalize_claim(t) for t in texts]
    vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True).fit([r["normalized"] for r in rows] + norms)
    sims = cosine_similarity(vec.transform(norms), vec.transform([r["normalized"] for r in rows]))
    for i, n in enumerate(norms):
        if n in by_norm:
            out.append({**by_norm[n], "match": "exact", "similarity": 1.0})
            continue
        j = int(sims[i].argmax())
        score = float(sims[i][j])
        out.append({**rows[j], "match": "similar", "similarity": round(score, 3)} if score >= SIMILARITY_THRESHOLD else None)
    return out


def list_library(db: OpsDB, limit: int = 200) -> List[Dict[str, Any]]:
    return db.query("SELECT text, claim_type, verdict, confidence, product_ids, review_id, ts, uses FROM claims_library "
                    "ORDER BY ts DESC LIMIT ?", (limit,))
