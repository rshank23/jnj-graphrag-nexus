"""MLR pre-review orchestration: extract -> verify -> check -> score; persistence, decisions, library and DOCX report."""
from __future__ import annotations

import json
import time
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from app.core.db import OpsDB, get_db, utcnow
from app.core.docx import DocxBuilder
from app.guardrails import CLINICAL_DISCLAIMER, sanitize_ingested_text
from app.mlr import library
from app.mlr.checks import SEVERITY_ORDER, run_checks
from app.mlr.claims import extract_claims

if TYPE_CHECKING:  # pragma: no cover
    from app.graph.graph_store import GraphStore

SEVERITY_WEIGHT = {"critical": 25, "warning": 8, "unverified": 5, "info": 1}
DECISIONS = ("accepted", "rejected", "revision")


def _readiness(findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in SEVERITY_ORDER}
    risk = min(100, sum(SEVERITY_WEIGHT[f["severity"]] for f in findings))
    status = "not-ready" if counts["critical"] else ("needs-review" if counts["warning"] or counts["unverified"] else "ready-for-mlr")
    return {"severity_counts": counts, "risk_score": risk, "status": status}


def _suggest(claim_text: str, finding: Dict[str, Any]) -> Optional[str]:
    from app.llm.router import get_router

    evidence = "; ".join(e["name"] for e in finding.get("evidence", [])[:3]) or "none"
    c = get_router().complete("mlr_suggest_revision", temperature=0.2, claim=claim_text, issue=finding["detail"], evidence=evidence)
    return c.text.strip() if c else None


def run_review(store: "GraphStore", text: str, title: Optional[str] = None, actor: Optional[str] = None,
               use_llm: bool = True, db: Optional[OpsDB] = None) -> Dict[str, Any]:
    db = db or get_db()
    t0 = time.perf_counter()
    clean, removed = sanitize_ingested_text(text)
    claims = extract_claims(store, clean, llm=use_llm)
    checked = run_checks(store, clean, claims)
    matches = library.lookup(db, [c.text for c in claims])
    claim_by_id = {c.id: c for c in claims}
    if use_llm:
        for f in checked["findings"]:
            if f["severity"] in ("critical", "warning") and f["claim_id"]:
                rev = _suggest(claim_by_id[f["claim_id"]].text, f)
                if rev:
                    f["llm_revision"] = rev
    claims_out = []
    for c, m in zip(claims, matches):
        v = checked["verifications"][c.id]
        claims_out.append({**c.to_dict(), "verdict": v["verdict"], "confidence": v["confidence"], "verification": v,
                           "library_match": m, "finding_ids": [f["id"] for f in checked["findings"] if f["claim_id"] == c.id]})
    review_id = uuid.uuid4().hex[:12]
    verdicts: Dict[str, int] = {}
    for c in claims_out:
        verdicts[c["verdict"]] = verdicts.get(c["verdict"], 0) + 1
    result = {
        "review_id": review_id, "title": title or "Untitled asset", "created": utcnow(), "actor": actor,
        "asset_text": clean, "sanitized_lines": removed, "claims": claims_out, "findings": checked["findings"],
        "summary": {**_readiness(checked["findings"]), "claims": len(claims_out), "verdicts": verdicts,
                    "products": sorted({p for c in claims for p in c.product_ids}),
                    "library_matches": sum(1 for m in matches if m)},
        "latency_ms": round((time.perf_counter() - t0) * 1000, 1), "disclaimer": CLINICAL_DISCLAIMER,
    }
    db.execute("INSERT INTO mlr_reviews (id, ts, title, actor, asset_text, result) VALUES (?,?,?,?,?,?)",
               (review_id, result["created"], result["title"], actor, clean, json.dumps(result, default=str)))
    db.audit("mlr.review", review_id, {"title": result["title"], "claims": len(claims_out), **result["summary"]["severity_counts"]}, actor)
    return result


def get_review(review_id: str, db: Optional[OpsDB] = None) -> Optional[Dict[str, Any]]:
    db = db or get_db()
    rows = db.query("SELECT result FROM mlr_reviews WHERE id=?", (review_id,))
    if not rows:
        return None
    result = json.loads(rows[0]["result"])
    result["decisions"] = db.query("SELECT ts, finding_id, decision, rationale, reviewer FROM finding_decisions WHERE review_id=? ORDER BY id",
                                   (review_id,))
    latest = {d["finding_id"]: d for d in result["decisions"]}
    for f in result["findings"]:
        f["decision"] = latest.get(f["id"])
    return result


def list_reviews(db: Optional[OpsDB] = None, limit: int = 50) -> List[Dict[str, Any]]:
    db = db or get_db()
    out = []
    for r in db.query("SELECT id, ts, title, actor, result FROM mlr_reviews ORDER BY ts DESC LIMIT ?", (limit,)):
        res = json.loads(r["result"])
        n_dec = db.query("SELECT COUNT(DISTINCT finding_id) n FROM finding_decisions WHERE review_id=?", (r["id"],))[0]["n"]
        out.append({"review_id": r["id"], "created": r["ts"], "title": r["title"], "actor": r["actor"], "summary": res["summary"],
                    "findings": len(res["findings"]), "decided": n_dec})
    return out


def record_decision(review_id: str, finding_id: str, decision: str, rationale: Optional[str], reviewer: Optional[str],
                    db: Optional[OpsDB] = None) -> Dict[str, Any]:
    db = db or get_db()
    if decision not in DECISIONS:
        raise ValueError(f"decision must be one of {DECISIONS}")
    review = get_review(review_id, db)
    if review is None:
        raise KeyError(review_id)
    if finding_id not in {f["id"] for f in review["findings"]}:
        raise KeyError(finding_id)
    db.execute("INSERT INTO finding_decisions (ts, review_id, finding_id, decision, rationale, reviewer) VALUES (?,?,?,?,?,?)",
               (utcnow(), review_id, finding_id, decision, rationale, reviewer))
    db.audit("mlr.decision", f"{review_id}/{finding_id}", {"decision": decision, "rationale": rationale}, reviewer)
    return {"review_id": review_id, "finding_id": finding_id, "decision": decision}


def approve_claim(review_id: str, claim_id: str, reviewer: Optional[str], db: Optional[OpsDB] = None) -> Dict[str, Any]:
    db = db or get_db()
    review = get_review(review_id, db)
    if review is None:
        raise KeyError(review_id)
    claim = next((c for c in review["claims"] if c["id"] == claim_id), None)
    if claim is None:
        raise KeyError(claim_id)
    out = library.add_claim(db, claim["text"], (claim["claim_types"] or [None])[0], "approved", claim["confidence"],
                            claim["product_ids"], review_id)
    db.audit("mlr.claim_approved", f"{review_id}/{claim_id}", {"text": claim["text"][:300]}, reviewer)
    return out


# --------------------------------------------------------------------------- DOCX report
_SEV_COLOR = {"critical": "B91C1C", "warning": "B45309", "unverified": "6B7280", "info": "1D4ED8"}


def review_docx(review: Dict[str, Any]) -> bytes:
    s = review["summary"]
    doc = DocxBuilder(f"MLR Pre-Review: {review['title']}")
    doc.heading(f"MLR Pre-Review Report \u2014 {review['title']}", 0)
    doc.paragraph(("Review ID: ", {"bold": True}), review["review_id"], ("   Created: ", {"bold": True}), review["created"],
                  ("   Reviewer: ", {"bold": True}), review.get("actor") or "\u2014")
    doc.paragraph(("Readiness: ", {"bold": True}), (s["status"].upper(), {"bold": True, "color": "B91C1C" if s["status"] == "not-ready" else "15803D"}),
                  f"   Risk score {s['risk_score']}/100   Claims {s['claims']}   Library matches {s['library_matches']}")
    doc.table(["Severity", "Count"], [[k.title(), str(v)] for k, v in s["severity_counts"].items()], [3000, 1500])
    doc.heading("Findings", 1)
    decisions = {d["finding_id"]: d for d in review.get("decisions", [])}
    rows = []
    for f in review["findings"]:
        d = decisions.get(f["id"])
        rows.append([f["id"], f["severity"].upper(), f["title"], f["detail"], f["suggestion"] or "",
                     "\n".join(p["regulation"] for p in f["precedents"]) or "\u2014",
                     f"{d['decision']} ({d['reviewer'] or 'n/a'})" if d else "pending"])
    doc.table(["ID", "Severity", "Finding", "Detail", "Suggested revision", "Regulation", "Decision"], rows,
              [500, 900, 1500, 2600, 1900, 1300, 1000])
    doc.heading("Claims & Evidence", 1)
    for c in review["claims"]:
        doc.paragraph((f"{c['id']} ", {"bold": True}), (f"[{c['verdict']}] ", {"bold": True, "color": _SEV_COLOR.get(
            "critical" if c["verdict"] == "contradicted" else "warning" if c["verdict"] == "unsupported" else "info")}), c["text"])
        for e in c["verification"].get("evidence", [])[:3]:
            doc.bullet(e["name"], (f"  {e['source_url']}" if e.get("source_url") else "", {"italic": True, "color": "6B7280"}), level=1)
    doc.heading("Asset text (as reviewed)", 1)
    for para in review["asset_text"].split("\n"):
        if para.strip():
            doc.paragraph(para)
    doc.paragraph((CLINICAL_DISCLAIMER.strip("_"), {"italic": True, "color": "6B7280", "size": 8}))
    return doc.to_bytes()
