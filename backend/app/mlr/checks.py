"""Evidence verification and compliance checks for extracted claims.

Each check returns findings: ``{id, claim_id, check, severity, title, detail, evidence, suggestion, precedents, anchor}``.
Severity: critical (must fix before submission), warning (reviewer judgement), unverified (no evidence found), info.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, Set

from app.guardrails import SAFETY_TERMS, UNSUPPORTED_CLAIM_PATTERNS
from app.mlr.claims import Claim
from app.mlr.precedent import precedents_for
from app.models.schemas import EdgeType, NodeType
from app.rag.hybrid_retriever import get_retriever, tokenize

if TYPE_CHECKING:  # pragma: no cover
    from app.graph.graph_store import GraphStore

SEVERITY_ORDER = ["critical", "warning", "unverified", "info"]
STALE_YEARS = 10
RELATIONAL_EDGES = {EdgeType.COMPATIBLE_ACCESSORY.value, EdgeType.COMPATIBLE_COUPLING.value, EdgeType.INTEGRATES_WITH.value,
                    EdgeType.SYNERGISTIC_PATHWAY_WITH.value, EdgeType.PRIMARY_PLATFORM_FOR.value, EdgeType.AUTO_SEGMENTS_3D_CT.value,
                    EdgeType.GUIDES_TRANSSEPTAL_PUNCTURE.value, EdgeType.POST_OP_INFECTION_CONTROL_FOR.value,
                    EdgeType.POST_OP_DRAINAGE_FOR.value}
POSITIVE_SAFETY = re.compile(r"\b(?:safe|well[- ]tolerated|favou?rable safety|minimal (?:side effects|risk)|low risk|reliable)\b", re.I)
NEGATED_RISK = re.compile(r"\bno (?:boxed warning|serious (?:side effects|risks?)|safety concerns?|known risks?)\b|\bwithout (?:any )?(?:serious )?(?:side effects|risks?)\b", re.I)
SUPERLATIVE = re.compile(r"\b(?:superior|best|#1|number one|first[- ]and[- ]only|unmatched|unrivall?ed|more effective than|better than|"
                         r"outperform\w*|leading)\b", re.I)
HEAD_TO_HEAD = re.compile(r"head[- ]to[- ]head|versus|vs\.?|compared with|comparator", re.I)
RISK_LANGUAGE = re.compile(r"boxed warning|important safety information|warnings? and precautions|contraindicat|adverse (?:reactions?|events?)|"
                           r"side effects|risks?\b|see full prescribing information", re.I)


class _Ctx:
    def __init__(self, store: "GraphStore", text: str):
        self.store = store
        self.text = text
        self.retriever = get_retriever(store)
        self._n = 0

    def node(self, nid: str) -> Dict[str, Any]:
        return self.store.graph.nodes[nid]

    def brand(self, nid: str) -> str:
        return self.node(nid)["name"].split(" (")[0]

    def next_id(self) -> str:
        self._n += 1
        return f"F{self._n}"

    def evidence_ref(self, nid: str) -> Dict[str, Any]:
        d = self.node(nid)
        props = d.get("properties", {})
        return {"node_id": nid, "name": d["name"], "label": d["label"], "source_url": props.get("source_url"),
                "published": props.get("published")}

    def targets(self, nid: str, relation: str) -> List[str]:
        return [t for _, t, _ in self.store.out_edges(nid, relation)]


def _finding(ctx: _Ctx, claim: Optional[Claim], check: str, severity: str, title: str, detail: str,
             evidence: Sequence[Dict[str, Any]] = (), suggestion: Optional[str] = None,
             anchor: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
    return {"id": ctx.next_id(), "claim_id": claim.id if claim else None, "check": check, "severity": severity, "title": title,
            "detail": detail, "evidence": list(evidence), "suggestion": suggestion, "precedents": precedents_for(check),
            "anchor": anchor or ({"start": claim.start, "end": claim.end} if claim else None)}


# --------------------------------------------------------------------------- evidence verification
def verify_claim(ctx: _Ctx, claim: Claim) -> Dict[str, Any]:
    """Retrieve evidence for the claim and grade support: supported / partial / unsupported / contradicted / no_evidence."""
    query = claim.text if not claim.product_ids else f"{claim.text} {' '.join(ctx.brand(p) for p in claim.product_ids)}"
    res = ctx.retriever.retrieve(query, top_k=6)
    allowed: Set[str] = set(claim.product_ids)
    for pid in claim.product_ids:
        allowed |= {t for _, t, _ in ctx.store.out_edges(pid)} | {s for s, _, _ in ctx.store.in_edges(pid)}
    passages = [p for p in res["reranked_passages"] if p["type"] == "passage" and (not allowed or set(p["node_ids"]) & allowed)]
    if not passages:
        return {"verdict": "no_evidence", "confidence": 0.0, "evidence": [], "support": 0.0}
    claim_toks = {t for t in tokenize(claim.text) if not t.isdigit()}
    best, best_p = 0.0, passages[0]
    for p in passages:
        toks = set(tokenize(p["text"]))
        cov = len(claim_toks & toks) / max(1, len(claim_toks))
        score = 0.65 * cov + 0.35 * p["cross_encoder_score"]
        if score > best:
            best, best_p = score, p
    nums = [re.sub(r"\s", "", n.lower()) for n in claim.numbers if re.search(r"%|percent|month|week|year|fold", n, re.I)]
    corpus = " ".join(p["text"].lower().replace(" ", "") for p in passages)
    nums_ok = all(n.replace("percent", "%") in corpus for n in nums)
    if NEGATED_RISK.search(claim.text) and any(ctx.targets(pid, EdgeType.HAS_BOXED_WARNING.value) for pid in claim.product_ids):
        verdict = "contradicted"
    elif best >= 0.55 and nums_ok:
        verdict = "supported"
    elif best >= 0.35:
        verdict = "partial"
    else:
        verdict = "unsupported"
    if nums and not nums_ok and verdict == "supported":
        verdict = "partial"
    ev = [ctx.evidence_ref(n) for p in passages[:3] for n in p["node_ids"][:1]]
    return {"verdict": verdict, "confidence": round(min(1.0, best), 3), "support": round(best, 3), "numbers_verified": nums_ok,
            "unverified_numbers": [] if nums_ok else nums, "evidence": ev,
            "best_passage": {"id": best_p["id"], "name": best_p["name"], "text": best_p["text"][:400]}}


def evidence_findings(ctx: _Ctx, claim: Claim, v: Dict[str, Any]) -> List[Dict[str, Any]]:
    verdict = v["verdict"]
    if verdict == "contradicted":
        bws = [ctx.evidence_ref(b) for pid in claim.product_ids for b in ctx.targets(pid, EdgeType.HAS_BOXED_WARNING.value)]
        return [_finding(ctx, claim, "contradicted", "critical", "Claim contradicts labeled safety information",
                         "The claim denies or minimizes risk, but the product carries a boxed warning in the knowledge graph.",
                         bws, "Remove risk-minimizing language and present the boxed warning with equal prominence.")]
    if verdict == "unsupported":
        return [_finding(ctx, claim, "unsupported", "warning", "Claim not supported by retrieved evidence",
                         f"Best evidence support score {v['support']:.2f} is below the 0.35 threshold.", v["evidence"],
                         "Cite the specific label section or study that substantiates this statement, or revise it.")]
    if verdict == "no_evidence":
        return [_finding(ctx, claim, "no_evidence", "unverified", "No evidence found for claim",
                         "No label, IFU or study in the graph substantiates this claim; reviewer must supply a reference.", [],
                         "Attach a reference (label section, CSR, publication) before submission.")]
    if v.get("unverified_numbers"):
        return [_finding(ctx, claim, "unsupported", "warning", "Quantitative data not found in cited evidence",
                         f"Numbers {v['unverified_numbers']} were not found in the retrieved label/IFU/study passages.", v["evidence"],
                         "Verify each figure against the source table and cite it.")]
    return []


# --------------------------------------------------------------------------- claim-level compliance checks
def check_absolute(ctx: _Ctx, claim: Claim) -> List[Dict[str, Any]]:
    out = []
    for pat, why in UNSUPPORTED_CLAIM_PATTERNS:
        m = pat.search(claim.text)
        if m:
            out.append(_finding(ctx, claim, "absolute_claim", "critical", why, f"Absolute language: '{m.group(0)}'.", [],
                                "Replace absolute wording with the labeled, study-specific result.",
                                {"start": claim.start + m.start(), "end": claim.start + m.end()}))
    return out


def check_comparative(ctx: _Ctx, claim: Claim) -> List[Dict[str, Any]]:
    m = SUPERLATIVE.search(claim.text)
    if not m:
        return []
    h2h = any("head-to-head" in str(ctx.node(e).get("properties", {})).lower() or HEAD_TO_HEAD.search(str(ctx.node(e).get("properties", {})))
              for pid in claim.product_ids for e in ctx.targets(pid, EdgeType.SUPPORTED_BY_EVIDENCE.value))
    return [_finding(ctx, claim, "comparative", "info" if h2h else "warning", "Comparative / superlative claim",
                     f"'{m.group(0)}' requires substantial evidence from adequate head-to-head trials"
                     + (" (comparative evidence present in graph; confirm design)." if h2h else "; none found in the graph."),
                     [], "Qualify with the specific trial, comparator and endpoint, or remove the superlative.",
                     {"start": claim.start + m.start(), "end": claim.start + m.end()})]


def check_off_label(ctx: _Ctx, claim: Claim) -> List[Dict[str, Any]]:
    out = []
    for pid in claim.product_ids:
        indicated = set(ctx.targets(pid, EdgeType.INDICATED_FOR.value))
        contraindicated = set(ctx.targets(pid, EdgeType.CONTRAINDICATED_WITH.value))
        if not indicated and ctx.node(pid)["label"] != NodeType.Product.value:
            continue
        for cid in claim.condition_ids:
            if cid in indicated or cid in contraindicated:
                continue
            if indicated:
                out.append(_finding(ctx, claim, "off_label", "critical", "Possible off-label indication",
                                    f"{ctx.brand(pid)} is not INDICATED_FOR '{ctx.node(cid)['name']}' in the graph. Labeled: "
                                    f"{', '.join(ctx.node(i)['name'] for i in sorted(indicated)) or 'none'}.",
                                    [ctx.evidence_ref(e) for e in ctx.targets(pid, EdgeType.SUPPORTED_BY_EVIDENCE.value)[:2]],
                                    "Restrict the claim to the approved indication(s)."))
        for cond in claim.off_graph_conditions:
            out.append(_finding(ctx, claim, "off_label", "critical", "Condition outside approved labeling",
                                f"'{cond}' is not an approved indication for {ctx.brand(pid)}.", [],
                                "Remove the reference to unapproved uses."))
        if claim.populations and "pediatric" not in str(ctx.node(pid).get("properties", {}).get("indication", "")).lower():
            out.append(_finding(ctx, claim, "population", "warning", "Population not in labeled indication",
                                f"Mentions {claim.populations}; the labeled indication for {ctx.brand(pid)} does not cover this population.",
                                [], "Confirm the population against the label (Use in Specific Populations)."))
    return out


def check_contraindication(ctx: _Ctx, claim: Claim) -> List[Dict[str, Any]]:
    out = []
    for pid in claim.product_ids:
        for cid in set(claim.condition_ids) & set(ctx.targets(pid, EdgeType.CONTRAINDICATED_WITH.value)):
            if re.search(r"\b(?:not|never|do not|contraindicated)\b", claim.text, re.I):
                continue
            out.append(_finding(ctx, claim, "contraindication", "critical", "Claim conflicts with a contraindication",
                                f"{ctx.brand(pid)} is CONTRAINDICATED_WITH '{ctx.node(cid)['name']}'.", [ctx.evidence_ref(cid)],
                                "Remove the suggestion of use in this setting and present the contraindication."))
    return out


def check_cross_product(ctx: _Ctx, claim: Claim) -> List[Dict[str, Any]]:
    prods = list(dict.fromkeys(claim.product_ids))
    if len(prods) < 2 or not re.search(r"\b(?:with|together|combin\w+|plus|alongside|integrat\w+|compatible|paired)\b", claim.text, re.I):
        return []
    out = []
    for i, a in enumerate(prods):
        for b in prods[i + 1:]:
            rels = {d["relation"] for _, t, d in ctx.store.out_edges(a) if t == b} | {d["relation"] for _, t, d in ctx.store.out_edges(b) if t == a}
            if not rels & RELATIONAL_EDGES:
                out.append(_finding(ctx, claim, "cross_product", "warning", "Combination / compatibility not substantiated",
                                    f"No compatibility, integration or synergy relationship between {ctx.brand(a)} and {ctx.brand(b)} "
                                    "in the knowledge graph.", [], "Remove the combined-use claim or cite labeling supporting it."))
    return out


def check_citations(ctx: _Ctx, claim: Claim) -> List[Dict[str, Any]]:
    year_now = datetime.now(timezone.utc).year
    old = [y for y in claim.reference_years if year_now - y > STALE_YEARS]
    if not old:
        return []
    return [_finding(ctx, claim, "stale_citation", "info", "Citation may be outdated",
                     f"Reference year(s) {old} are more than {STALE_YEARS} years old.", [],
                     "Confirm the reference reflects current labeling and the latest data.")]


def check_safety_signals(ctx: _Ctx, claim: Claim) -> List[Dict[str, Any]]:
    if not POSITIVE_SAFETY.search(claim.text):
        return []
    out = []
    for pid in claim.product_ids:
        sigs = [s for s in ctx.targets(pid, EdgeType.HAS_SAFETY_SIGNAL.value) if ctx.node(s).get("properties", {}).get("is_signal")]
        recalls = [r for r in ctx.targets(pid, EdgeType.HAS_RECALL.value)
                   if "class i" == str(ctx.node(r).get("properties", {}).get("classification", "")).lower().strip()]
        bws = ctx.targets(pid, EdgeType.HAS_BOXED_WARNING.value)
        if sigs or recalls or bws:
            parts = []
            if bws:
                parts.append("a boxed warning")
            if sigs:
                parts.append(f"FAERS disproportionality signals ({', '.join(ctx.node(s)['properties']['reaction'] for s in sigs[:4])})")
            if recalls:
                parts.append(f"{len(recalls)} Class I recall(s)")
            out.append(_finding(ctx, claim, "safety_signal", "warning", "Favourable safety language despite known risks",
                                f"{ctx.brand(pid)} has {' and '.join(parts)}.", [ctx.evidence_ref(x) for x in (bws + sigs + recalls)[:4]],
                                "Avoid general safety characterisations; present specific labeled safety data."))
    return out


def check_label_change(ctx: _Ctx, claim: Claim) -> List[Dict[str, Any]]:
    out = []
    for pid in claim.product_ids:
        changes = [c for c in ctx.targets(pid, EdgeType.HAS_LABEL_CHANGE.value)]
        if changes:
            latest = changes[-1]
            sev = ctx.node(latest).get("properties", {}).get("severity", "info")
            out.append(_finding(ctx, claim, "label_change", "warning" if sev == "critical" else "info", "Label recently changed",
                                f"{ctx.node(latest)['name']} changed sections {ctx.node(latest).get('properties', {}).get('sections_changed')}.",
                                [ctx.evidence_ref(latest)], "Re-verify the claim against the current label version."))
    return out


CLAIM_CHECKS = [check_absolute, check_comparative, check_off_label, check_contraindication, check_cross_product, check_citations,
                check_safety_signals, check_label_change]


# --------------------------------------------------------------------------- asset-level checks
def check_safety_omission(ctx: _Ctx, claims: List[Claim]) -> List[Dict[str, Any]]:
    out = []
    products = list(dict.fromkeys(p for c in claims for p in c.product_ids))
    for pid in products:
        bws = ctx.targets(pid, EdgeType.HAS_BOXED_WARNING.value)
        if not bws:
            continue
        bw_text = " ".join(str(ctx.node(b).get("properties", {}).get("warning_text", "")) for b in bws) + " " + str(
            ctx.node(pid).get("properties", {}).get("boxed_warning", ""))
        key_terms = {t for t in tokenize(bw_text) if len(t) > 6}
        mentioned = "boxed warning" in ctx.text.lower() or len(key_terms & set(tokenize(ctx.text))) >= 2
        if not mentioned:
            first = next(c for c in claims if pid in c.product_ids)
            out.append(_finding(ctx, first, "safety_omission", "critical", "Boxed warning omitted",
                                f"{ctx.brand(pid)} carries a boxed warning ({bw_text.strip()[:220]}) that the asset does not present.",
                                [ctx.evidence_ref(b) for b in bws],
                                "Add the boxed warning and Important Safety Information with fair-balance prominence."))
    return out


def check_fair_balance(ctx: _Ctx, claims: List[Claim]) -> List[Dict[str, Any]]:
    benefit = [c for c in claims if {"efficacy", "comparative"} & set(c.claim_types)]
    if not benefit or RISK_LANGUAGE.search(ctx.text) or SAFETY_TERMS.search(ctx.text):
        return []
    return [_finding(ctx, None, "fair_balance", "critical" if len(benefit) >= 2 else "warning", "No risk information (fair balance)",
                     f"{len(benefit)} benefit claim(s) but no risk / Important Safety Information in the asset.", [],
                     "Add Important Safety Information with prominence comparable to benefit claims.", {"start": 0, "end": 0})]


ASSET_CHECKS = [check_safety_omission, check_fair_balance]


def run_checks(store: "GraphStore", text: str, claims: List[Claim]) -> Dict[str, Any]:
    ctx = _Ctx(store, text)
    verifications: Dict[str, Dict[str, Any]] = {}
    findings: List[Dict[str, Any]] = []
    for claim in claims:
        v = verify_claim(ctx, claim)
        verifications[claim.id] = v
        findings += evidence_findings(ctx, claim, v)
        for chk in CLAIM_CHECKS:
            findings += chk(ctx, claim)
    for chk in ASSET_CHECKS:
        findings += chk(ctx, claims)
    findings.sort(key=lambda f: (SEVERITY_ORDER.index(f["severity"]), f["anchor"]["start"] if f["anchor"] else 0))
    return {"verifications": verifications, "findings": findings}
