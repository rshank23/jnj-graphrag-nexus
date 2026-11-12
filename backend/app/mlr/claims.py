"""Claim segmentation, typing and entity anchoring for promotional assets (MLR pre-review)."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from app.models.schemas import NodeType
from app.rag.entity_resolver import get_resolver

if TYPE_CHECKING:  # pragma: no cover
    from app.graph.graph_store import GraphStore

CLAIM_TYPES: List[Tuple[str, re.Pattern[str]]] = [(t, re.compile(p, re.I)) for t, p in (
    ("comparative", r"\b(?:superior|better|more effective|outperform\w*|versus|vs\.?|compared (?:to|with)|than|best|#1|number one|"
                    r"leading|first[- ]and[- ]only|only\b|unmatched|unrivall?ed)"),
    ("safety", r"\b(?:safe|safety|well[- ]tolerated|tolerab\w+|side[- ]effects?|adverse|risk|warning|contraindicat\w*)"),
    ("efficacy", r"\b(?:effective|efficacy|response rate|remission|reduc\w+|improv\w+|surviv\w+|cure\w*|relie\w+|"
                 r"achiev\w+|clear(?:ance|er)?|PASI|ACR\d*|endpoint|outcomes?)"),
    ("mechanism", r"\b(?:mechanism|targets?|inhibit\w*|blocks?|binds?|agonist|antagonist|antibod\w+|CAR-T|receptor|pathway)"),
    ("dosing", r"\b(?:dose|dosing|mg\b|once[- ](?:daily|weekly|monthly)|every \d+ weeks?|administ\w+|infusion|injection|tablet)"),
    ("economic", r"\b(?:cost|savings?|value|reimburs\w+|budget|economic|length of stay|readmission\w*)"),
    ("indication", r"\b(?:indicated|approved for|treat(?:s|ment of|ing)?|for (?:adults|patients|people) with)"),
    ("epidemiology", r"\b(?:prevalence|incidence|affects? (?:\d|over|nearly|about|up to)|million (?:people|patients|americans))"),
)]
NUMERIC = re.compile(r"\b\d+(?:\.\d+)?\s?(?:%|percent|months?|weeks?|years?|mg|fold|x)\b|\b\d+(?:\.\d+)?\b", re.I)
CITATION_REF = re.compile(r"\[(\d+(?:[,\u2013-]\s*\d+)*)\]|\(([A-Z][A-Za-z-]+(?: et al\.?)?,? (?:19|20)\d{2})\)")
YEAR = re.compile(r"\b(19[89]\d|20[0-3]\d)\b")
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"\u201c(\[])|\n{1,}")

# Conditions not modelled in the graph that commonly appear in off-label promotion; any mention is off-label for every product.
OFF_GRAPH_CONDITIONS = [
    "breast cancer", "alzheimer", "dementia", "anxiety", "insomnia", "obesity", "weight loss", "diabetes", "migraine", "covid",
    "autism", "chronic pain", "fibromyalgia", "lupus", "asthma", "atopic dermatitis", "eczema", "glioblastoma", "pancreatic cancer",
]
POPULATION_TERMS = re.compile(r"\b(?:pediatric|paediatric|children|child|adolescents?|infants?|pregnan\w+|neonat\w+)\b", re.I)


@dataclass
class Claim:
    id: str
    text: str
    start: int
    end: int
    claim_types: List[str]
    product_ids: List[str] = field(default_factory=list)
    condition_ids: List[str] = field(default_factory=list)
    off_graph_conditions: List[str] = field(default_factory=list)
    populations: List[str] = field(default_factory=list)
    numbers: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)
    reference_years: List[int] = field(default_factory=list)
    source: str = "rules"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def segment(text: str) -> List[Tuple[int, int, str]]:
    """Sentence spans with character offsets into the original asset."""
    spans: List[Tuple[int, int, str]] = []
    pos = 0
    for part in SENTENCE_SPLIT.split(text):
        if part is None:
            continue
        idx = text.find(part, pos)
        if idx < 0:
            continue
        stripped = part.strip()
        if stripped:
            start = idx + (len(part) - len(part.lstrip()))
            spans.append((start, start + len(stripped), stripped))
        pos = idx + len(part)
    return spans


def condition_lexicon(store: "GraphStore") -> List[Tuple[str, str]]:
    """(surface form, condition id), longest first. Derived from ClinicalCondition node names."""
    lex: List[Tuple[str, str]] = []
    for nid, d in store.graph.nodes(data=True):
        if d["label"] != NodeType.ClinicalCondition.value:
            continue
        name = d["name"].lower()
        forms = {name, name.split(" (")[0]}
        for piece in re.split(r"\s*(?:/|&|\bor\b|\band\b|,)\s*", name.split(" (")[0]):
            piece = re.sub(r"^(?:moderate-to-severe|active|recurrent|metastatic|end-stage|severely|generalized|treatment-resistant)\s+", "", piece).strip()
            if len(piece) >= 6:
                forms.add(piece)
        abbrev = re.search(r"\(([A-Za-z0-9-]{2,8})\)", d["name"])
        if abbrev:
            forms.add(abbrev.group(1).lower())
        lex += [(f, nid) for f in forms if f]
    return sorted(set(lex), key=lambda x: -len(x[0]))


def _match_conditions(sentence: str, lexicon: List[Tuple[str, str]]) -> List[str]:
    s = sentence.lower()
    found: List[str] = []
    for form, cid in lexicon:
        if re.search(rf"(?<![a-z]){re.escape(form)}(?![a-z])", s) and cid not in found:
            found.append(cid)
    return found


def _is_claim(sentence: str, types: List[str], products: List[str]) -> bool:
    if len(sentence) < 15 or sentence.isupper() and len(sentence) < 60:
        return False
    return bool(types) and (bool(products) or bool(NUMERIC.search(sentence)) or "comparative" in types or "safety" in types)


def extract_claims(store: "GraphStore", text: str, llm: bool = True) -> List[Claim]:
    resolver = get_resolver(store)
    lexicon = condition_lexicon(store)
    claims: List[Claim] = []
    current_products: List[str] = []
    for start, end, sent in segment(text):
        products = [str(h["id"]) for h in resolver.resolve(sent)
                    if store.graph.nodes[str(h["id"])]["label"] in (NodeType.Product.value, NodeType.SoftwareModule.value)]
        if products:
            current_products = products
        types = [t for t, pat in CLAIM_TYPES if pat.search(sent)]
        if not _is_claim(sent, types, products):
            continue
        refs = [m.group(0) for m in CITATION_REF.finditer(sent)]
        claims.append(Claim(
            id=f"C{len(claims) + 1}", text=sent, start=start, end=end, claim_types=types,
            product_ids=products or list(current_products), condition_ids=_match_conditions(sent, lexicon),
            off_graph_conditions=[c for c in OFF_GRAPH_CONDITIONS if c in sent.lower()],
            populations=sorted({m.group(0).lower() for m in POPULATION_TERMS.finditer(sent)}),
            numbers=[m.group(0) for m in NUMERIC.finditer(sent) if not YEAR.fullmatch(m.group(0).strip())][:8],
            references=refs, reference_years=[int(y) for r in refs for y in YEAR.findall(r)]))
    if llm:
        claims += _llm_claims(store, text, claims, lexicon)
    return claims


def _llm_claims(store: "GraphStore", text: str, existing: List[Claim], lexicon: List[Tuple[str, str]]) -> List[Claim]:
    """Optional LLM pass to catch implicit claims the rules miss; results are anchored back to exact offsets."""
    from app.llm.router import get_router

    completion = get_router().complete("mlr_claim_extract", temperature=0.0, asset=text[:8000])
    if completion is None:
        return []
    try:
        payload = json.loads(re.search(r"\{.*\}|\[.*\]", completion.text, re.S).group(0))  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        return []
    items = payload.get("claims", []) if isinstance(payload, dict) else payload
    resolver = get_resolver(store)
    out: List[Claim] = []
    for item in items[:30]:
        quote = (item.get("text") if isinstance(item, dict) else str(item)) or ""
        idx = text.find(quote.strip())
        if not quote.strip() or idx < 0 or any(c.start <= idx < c.end for c in existing + out):
            continue
        products = [str(h["id"]) for h in resolver.resolve(quote)]
        out.append(Claim(id=f"C{len(existing) + len(out) + 1}", text=quote.strip(), start=idx, end=idx + len(quote.strip()),
                         claim_types=[(item.get("type") if isinstance(item, dict) else None) or "efficacy"], product_ids=products,
                         condition_ids=_match_conditions(quote, lexicon), source=f"llm:{completion.model}"))
    return out
