"""PyMuPDF FDA SPL section splitter and schema-constrained triplet extractor."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, Union

from app.graph.seed_data import IM, is_kenvue_brand
from app.models.schemas import EdgeType, GraphEdge, GraphNode, NodeType

if TYPE_CHECKING:  # pragma: no cover
    from app.graph.graph_store import GraphStore

SECTION_PATTERNS: Dict[str, re.Pattern[str]] = {
    "boxed_warning": re.compile(r"^\s*(?:BOXED\s+WARNING|WARNING\s*:\s*[A-Z][A-Z ,\-/&]+)", re.MULTILINE),
    "indications": re.compile(r"^\s*1\s+INDICATIONS\s+(?:AND|&)\s+USAGE\b", re.MULTILINE | re.IGNORECASE),
    "dosage": re.compile(r"^\s*2\s+DOSAGE\s+(?:AND|&)\s+ADMINISTRATION\b", re.MULTILINE | re.IGNORECASE),
    "contraindications": re.compile(r"^\s*4\s+CONTRAINDICATIONS\b", re.MULTILINE | re.IGNORECASE),
    "warnings_precautions": re.compile(r"^\s*5\s+WARNINGS\s+(?:AND|&)\s+PRECAUTIONS\b", re.MULTILINE | re.IGNORECASE),
    "mechanism": re.compile(r"^\s*12\.1\s+Mechanism\s+of\s+Action\b", re.MULTILINE | re.IGNORECASE),
    "pharmacodynamics": re.compile(r"^\s*12\.2\s+Pharmacodynamics\b", re.MULTILINE | re.IGNORECASE),
}
CAPTURED_SECTIONS = ("boxed_warning", "indications", "contraindications", "mechanism")
FRANCHISE_IDS = {
    "oncology": "FR_ONCOLOGY",
    "immunology": "FR_IMMUNOLOGY",
    "neuroscience": "FR_NEUROSCIENCE",
    "cardiopulmonary": "FR_CARDIOPULMONARY",
    "pulmonary hypertension": "FR_CARDIOPULMONARY",
    "infectious": "FR_INFECTIOUS_DISEASES",
    "electrophysiology": "FR_ELECTROPHYSIOLOGY",
    "surgery": "FR_SURGERY",
    "orthopaedics": "FR_ORTHOPAEDICS",
    "orthopedics": "FR_ORTHOPAEDICS",
    "interventional": "FR_INTERVENTIONAL_CV",
    "vision": "FR_VISION",
}
_FRANCHISE_KEYWORDS = [
    ("FR_ONCOLOGY", ("cancer", "carcinoma", "myeloma", "tumor", "lymphoma", "leukemia", "oncology")),
    ("FR_IMMUNOLOGY", ("psoriasis", "arthritis", "colitis", "crohn", "myasthenia", "immunology", "lupus")),
    ("FR_NEUROSCIENCE", ("depression", "schizophrenia", "bipolar", "adhd", "neuroscience", "epilepsy")),
    ("FR_CARDIOPULMONARY", ("pulmonary arterial hypertension", "pah", "thrombo", "cardiopulmonary")),
    ("FR_INFECTIOUS_DISEASES", ("hiv", "infection", "viral", "tuberculosis")),
]


def slugify(text: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", text.upper()).strip("_")[:60] or "UNNAMED"


def resolve_franchise_id(franchise: Optional[str], text: str = "") -> Optional[str]:
    if franchise:
        f = franchise.lower()
        for key, fid in FRANCHISE_IDS.items():
            if key in f:
                return fid
    lowered = text.lower()
    for fid, kws in _FRANCHISE_KEYWORDS:
        if any(re.search(rf"\b{re.escape(k)}", lowered) for k in kws):
            return fid
    return None


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


@dataclass
class LabelExtraction:
    product_name: str
    sections: Dict[str, str]
    nodes: List[GraphNode] = field(default_factory=list)
    edges: List[GraphEdge] = field(default_factory=list)


class FDALabelPDFExtractor:
    """Split FDA Structured Product Label PDFs into sections and emit graph triplets."""

    def extract_text(self, source: Union[str, Path, bytes]) -> str:
        try:
            import pymupdf as fitz  # PyMuPDF >= 1.24
        except ImportError:  # pragma: no cover
            import fitz  # type: ignore[no-redef]

        doc = fitz.open(stream=source, filetype="pdf") if isinstance(source, (bytes, bytearray)) else fitz.open(str(source))
        try:
            return "\n".join(page.get_text("text") for page in doc)
        finally:
            doc.close()

    def split_sections(self, text: str) -> Dict[str, str]:
        hits: List[Tuple[int, int, str]] = []
        for name, pattern in SECTION_PATTERNS.items():
            m = pattern.search(text)
            if m:
                hits.append((m.start(), m.end(), name))
        hits.sort()
        sections: Dict[str, str] = {}
        for i, (start, end, name) in enumerate(hits):
            stop = hits[i + 1][0] if i + 1 < len(hits) else len(text)
            body = text[start:stop]
            if name == "boxed_warning":
                body = text[start:stop]
            else:
                body = text[end:stop]
            if name in CAPTURED_SECTIONS:
                sections[name] = _clean(body)
        return sections

    @staticmethod
    def guess_product_name(text: str) -> str:
        m = re.search(r"([A-Z][A-Z0-9\-]{2,}(?:\s+[A-Z][A-Z0-9\-]{2,})?)\s*\(([a-z][^)]{2,80})\)", text)
        if m:
            return f"{m.group(1).strip()} ({m.group(2).strip()})"
        for line in text.splitlines():
            line = line.strip()
            if 3 <= len(line) <= 80 and line.isupper() and "WARNING" not in line and "HIGHLIGHTS" not in line:
                return line
        return "Unnamed FDA Label Product"

    @staticmethod
    def _conditions_from_indications(text: str) -> List[str]:
        found: List[str] = []
        for m in re.finditer(r"indicated\s+(?:for|as)\s+(?:the\s+)?(?:treatment\s+of\s+|chronic\s+treatment\s+of\s+)?([^.;]{5,160})", text, re.IGNORECASE):
            found.append(m.group(1))
        if not found:
            found = [s for s in re.split(r"[;.]\s+", text) if len(s) > 8][:3]
        cleaned = []
        for c in found:
            c = re.split(r"\s+(?:who|in adults|in adult patients|in patients)\b", c, maxsplit=1)[0]
            c = _clean(c).strip(" ,:")
            if c and c.lower() not in {x.lower() for x in cleaned}:
                cleaned.append(c[:120])
        return cleaned[:5]

    @staticmethod
    def _contraindications(text: str) -> List[str]:
        if not text or re.match(r"^\s*none\b", text, re.IGNORECASE):
            return []
        parts = re.split(r"(?:\s*[•\u2022]\s*|\.\s+|;\s+)", text)
        out = []
        for part in parts:
            part = _clean(part).strip(" ,:")
            part = re.sub(r"\(\s*[\d.,\s]+\)", "", part).strip()
            if len(part) >= 6 and not re.fullmatch(r"[\d.\s]+", part):
                out.append(part[:120])
        return out[:5]

    def to_triplets(
        self,
        sections: Dict[str, str],
        product_name: str,
        division: str = IM,
        franchise: Optional[str] = None,
        source_url: Optional[str] = None,
        doc_title: Optional[str] = None,
    ) -> LabelExtraction:
        if is_kenvue_brand(product_name):
            raise ValueError(f"'{product_name}' is a Kenvue consumer-health brand and cannot be ingested")
        all_text = " ".join(sections.values())
        franchise_id = resolve_franchise_id(franchise, sections.get("indications", "") + " " + all_text)
        pid = f"ING_{slugify(product_name.split('(')[0])}"
        props: Dict[str, object] = {"category": "Prescription Medicine", "ingested": True}
        if source_url:
            props["source_url"] = source_url
        if sections.get("indications"):
            props["indication"] = sections["indications"][:600]
        if sections.get("mechanism"):
            props["mechanism"] = sections["mechanism"][:600]
        if sections.get("contraindications"):
            props["contraindication"] = sections["contraindications"][:600]
        if sections.get("boxed_warning"):
            props["boxed_warning"] = sections["boxed_warning"][:600]

        from app.graph.seed_data import FRANCHISES

        franchise_name = next((f["name"] for f in FRANCHISES if f["id"] == franchise_id), franchise)
        nodes: List[GraphNode] = [GraphNode(id=pid, label=NodeType.Product, name=product_name, division=division,
                                            franchise=franchise_name, properties=props)]
        edges: List[GraphEdge] = []
        if franchise_id:
            edges.append(GraphEdge(source=pid, target=franchise_id, relation=EdgeType.IN_FRANCHISE))

        doc_id = f"DOC_{slugify(product_name.split('(')[0])}_LABEL"
        nodes.append(GraphNode(id=doc_id, label=NodeType.EvidenceDocument,
                               name=doc_title or f"FDA Prescribing Information: {product_name}", division=division,
                               properties={"doc_type": "FDA SPL", "source_url": source_url,
                                           "excerpt": _clean(all_text)[:1200], "sections": sorted(sections)}))
        edges.append(GraphEdge(source=pid, target=doc_id, relation=EdgeType.SUPPORTED_BY_EVIDENCE))

        if sections.get("boxed_warning"):
            bw_id = f"BW_{slugify(product_name.split('(')[0])}_ING"
            nodes.append(GraphNode(id=bw_id, label=NodeType.BoxedWarning, name=f"Boxed Warning: {product_name.split('(')[0].strip()}",
                                   division=division, properties={"warning_text": sections["boxed_warning"][:600]}))
            edges.append(GraphEdge(source=pid, target=bw_id, relation=EdgeType.HAS_BOXED_WARNING))
            edges.append(GraphEdge(source=bw_id, target=doc_id, relation=EdgeType.SUPPORTED_BY_EVIDENCE))

        for cond in self._conditions_from_indications(sections.get("indications", "")):
            cid = f"COND_{slugify(cond)}"
            nodes.append(GraphNode(id=cid, label=NodeType.ClinicalCondition, name=cond[:1].upper() + cond[1:], division=division))
            edges.append(GraphEdge(source=pid, target=cid, relation=EdgeType.INDICATED_FOR, properties={"source": "1 INDICATIONS AND USAGE"}))

        for ci in self._contraindications(sections.get("contraindications", "")):
            cid = f"COND_{slugify(ci)}"
            nodes.append(GraphNode(id=cid, label=NodeType.ClinicalCondition, name=ci[:1].upper() + ci[1:], division=division))
            edges.append(GraphEdge(source=pid, target=cid, relation=EdgeType.CONTRAINDICATED_WITH, properties={"source": "4 CONTRAINDICATIONS"}))

        return LabelExtraction(product_name=product_name, sections=sections, nodes=nodes, edges=edges)

    def extract(self, source: Union[str, Path, bytes], product_name: Optional[str] = None, **kwargs) -> LabelExtraction:
        text = self.extract_text(source)
        return self.extract_from_text(text, product_name=product_name, **kwargs)

    def extract_from_text(self, text: str, product_name: Optional[str] = None, **kwargs) -> LabelExtraction:
        sections = self.split_sections(text)
        if not sections:
            # Free-form product text: treat it as the indication / description body.
            sections = {"indications": _clean(text)[:2000]}
        name = product_name or self.guess_product_name(text)
        return self.to_triplets(sections, name, **kwargs)

    def ingest(self, store: "GraphStore", extraction: LabelExtraction) -> Tuple[List[GraphNode], List[GraphEdge]]:
        return store.bulk_upsert(extraction.nodes, extraction.edges, persist=True)
