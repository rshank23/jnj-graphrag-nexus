"""Input / output guardrails: PHI redaction, prompt-injection defence, unsupported-claim detection and confidence.

Design reference: ClinicalDocIntelligence ``InputGuardrails`` / ``OutputGuardrails`` (re-implemented, not copied).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    blocked = "blocked"


_RISK_ORDER = [RiskLevel.low, RiskLevel.medium, RiskLevel.high, RiskLevel.blocked]

PHI_PATTERNS: Dict[str, re.Pattern[str]] = {
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "mrn": re.compile(r"\b(?:MRN|medical record(?: number)?)[:#\s]*[A-Z0-9-]{5,}\b", re.I),
    "dob": re.compile(r"\b(?:DOB|date of birth|born on)[:\s]*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", re.I),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "phone": re.compile(r"(?<!\d)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?!\d)"),
    "patient_name": re.compile(r"\bpatient(?: name)?[:\s]+(?:Mr\.?|Mrs\.?|Ms\.?)?\s*[A-Z][a-z]+\s+[A-Z][a-z]+\b"),
}

INJECTION_PATTERNS: List[re.Pattern[str]] = [re.compile(p, re.I) for p in (
    r"ignore (?:all |any )?(?:the )?(?:previous|prior|above) (?:instructions|prompts|rules)",
    r"disregard (?:all |the )?(?:previous|prior|above|system)",
    r"you are now (?:a|an|in) ",
    r"(?:reveal|print|show|repeat) (?:your |the )?(?:system prompt|hidden instructions|instructions verbatim)",
    r"\bjailbreak\b|\bDAN mode\b|developer mode",
    r"</?(?:system|assistant)>|\[/?INST\]|<\|im_start\|>",
    r"act as (?:if you have no|an unrestricted)",
    r"override (?:the )?(?:safety|guardrails|compliance)",
)]

UNSUPPORTED_CLAIM_PATTERNS: List[Tuple[re.Pattern[str], str]] = [(re.compile(p, re.I), why) for p, why in (
    (r"\b(?:guaranteed|guarantees) to (?:cure|work|heal)", "Absolute efficacy guarantee"),
    (r"\b100\s?% (?:safe|effective|cure|success)", "Absolute safety/efficacy claim"),
    (r"\bno (?:known )?side[- ]effects\b", "Denial of adverse effects"),
    (r"\bcompletely (?:safe|risk[- ]free)\b|\brisk[- ]free\b", "Risk-free claim"),
    (r"\bcures? (?:cancer|depression|psoriasis|hiv)\b", "Cure claim"),
    (r"\bmiracle\b|\bbreakthrough cure\b", "Promotional hyperbole"),
)]

SAFETY_TERMS = re.compile(r"boxed warning|contraindicat|cytokine release|neurotoxicity|suicid|embryo-?fetal|abuse|dependence|"
                          r"secondary hematological malignanc|sedation|dissociation|hypotension", re.I)

CLINICAL_DISCLAIMER = ("_For internal J&J commercial, medical and MLR decision support only. Not medical advice. "
                       "Verify against the current FDA-approved labeling / IFU before external use._")


@dataclass
class GuardrailResult:
    text: str
    risk_level: RiskLevel = RiskLevel.low
    blocked: bool = False
    findings: List[Dict[str, str]] = field(default_factory=list)

    def escalate(self, level: RiskLevel) -> None:
        if _RISK_ORDER.index(level) > _RISK_ORDER.index(self.risk_level):
            self.risk_level = level

    def to_dict(self) -> Dict[str, Any]:
        return {"risk_level": self.risk_level.value, "blocked": self.blocked, "findings": self.findings}


def detect_phi(text: str) -> List[Tuple[str, str]]:
    return [(kind, m.group(0)) for kind, pat in PHI_PATTERNS.items() for m in pat.finditer(text)]


def redact_phi(text: str) -> Tuple[str, List[str]]:
    kinds: List[str] = []
    for kind, pat in PHI_PATTERNS.items():
        text, n = pat.subn(f"[REDACTED-{kind.upper()}]", text)
        if n:
            kinds.append(kind)
    return text, kinds


def detect_injection(text: str) -> List[str]:
    return [m.group(0) for pat in INJECTION_PATTERNS for m in [pat.search(text)] if m]


def check_input(query: str) -> GuardrailResult:
    """Screen a user query: block prompt injection, redact PHI (the POC must never store patient data)."""
    res = GuardrailResult(text=query)
    hits = detect_injection(query)
    if hits:
        res.blocked = True
        res.escalate(RiskLevel.blocked)
        res.findings.append({"type": "prompt_injection", "detail": f"Instruction-override pattern detected: '{hits[0]}'"})
        return res
    redacted, kinds = redact_phi(query)
    if kinds:
        res.text = redacted
        res.escalate(RiskLevel.medium)
        res.findings.append({"type": "phi_redacted", "detail": f"Redacted potential PHI ({', '.join(kinds)}) before processing and logging"})
    return res


def sanitize_ingested_text(text: str) -> Tuple[str, List[str]]:
    """Neutralise indirect prompt injection in scraped / uploaded content before it can reach an LLM."""
    removed: List[str] = []
    kept: List[str] = []
    for line in text.splitlines():
        if detect_injection(line):
            removed.append(line.strip()[:160])
            continue
        kept.append(line)
    cleaned = "\n".join(kept)
    cleaned = re.sub(r"</?(?:system|assistant|user)>|\[/?INST\]|<\|im_(?:start|end)\|>", " ", cleaned, flags=re.I)
    cleaned, _ = redact_phi(cleaned)
    return cleaned, removed


def find_unsupported_claims(text: str) -> List[Dict[str, str]]:
    out = []
    for pat, why in UNSUPPORTED_CLAIM_PATTERNS:
        m = pat.search(text)
        if m:
            out.append({"type": "unsupported_claim_language", "detail": f"{why}: '{m.group(0)}'"})
    return out


def estimate_confidence(passages: Sequence[Dict[str, Any]], citations: int, entity_mentions: int, provenance: Optional[float] = None) -> float:
    """Calibrated 0-1 heuristic from retrieval strength, grounding and entity resolution."""
    scores = sorted((float(p.get("cross_encoder_score", 0.0)) for p in passages), reverse=True)
    if not scores:
        return 0.0
    top = scores[0]
    mean3 = sum(scores[:3]) / min(3, len(scores))
    conf = 0.40 * top + 0.20 * mean3 + 0.20 * min(1.0, citations / 2.0) + 0.20 * (1.0 if entity_mentions else 0.4)
    if provenance is not None:
        conf = 0.75 * conf + 0.25 * provenance
    return round(max(0.0, min(1.0, conf)), 3)


def check_output(answer: str, citations: int, confidence: float, min_confidence: float, safety_context: bool) -> GuardrailResult:
    res = GuardrailResult(text=answer)
    for f in find_unsupported_claims(answer):
        res.findings.append(f)
        res.escalate(RiskLevel.high)
    if citations == 0:
        res.findings.append({"type": "no_citations", "detail": "Answer is not linked to any EvidenceDocument; treat as unverified"})
        res.escalate(RiskLevel.medium)
    if confidence < min_confidence:
        res.findings.append({"type": "low_confidence", "detail": f"Confidence {confidence:.2f} below threshold {min_confidence:.2f}"})
        res.escalate(RiskLevel.medium)
    if safety_context or SAFETY_TERMS.search(answer):
        res.findings.append({"type": "requires_medical_review",
                             "detail": "Answer contains boxed-warning / contraindication content; route to Medical Affairs before external use"})
        res.escalate(RiskLevel.medium)
    return res
