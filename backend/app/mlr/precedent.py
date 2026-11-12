"""Curated precedent categories paraphrased from recurring themes in public FDA OPDP / CDRH promotional enforcement letters.

These are generic, paraphrased category descriptions with the governing regulation. They are not quotations of specific letters
and are intended to show reviewers *why* a finding matters. Replace/extend with J&J's internal MLR precedent database in production.
"""
from __future__ import annotations

from typing import Dict, List

PRECEDENTS: Dict[str, Dict[str, str]] = {
    "risk_omission": {
        "category": "Omission or minimization of risk information",
        "summary": "Promotional pieces presenting efficacy without the boxed warning / most serious risks are a frequently cited "
                   "theme in OPDP untitled and warning letters.",
        "regulation": "21 CFR 202.1(e)(5)(ii); FD&C Act \u00a7502(n)",
    },
    "fair_balance": {
        "category": "Lack of fair balance",
        "summary": "Benefit claims must be balanced by risk information of comparable prominence and readability.",
        "regulation": "21 CFR 202.1(e)(5)(ii), (e)(7)(viii)",
    },
    "overstatement": {
        "category": "Overstatement of efficacy / unsubstantiated claims",
        "summary": "Claims of efficacy beyond what adequate and well-controlled studies demonstrate, including absolute language.",
        "regulation": "21 CFR 202.1(e)(6)(i); FD&C Act \u00a7502(a)",
    },
    "superiority": {
        "category": "Unsubstantiated superiority or comparative claims",
        "summary": "Comparative or 'best/first/only' claims require substantial evidence, typically head-to-head adequate and "
                   "well-controlled trials.",
        "regulation": "21 CFR 202.1(e)(6)(ii)",
    },
    "off_label": {
        "category": "Broadening of indication / off-label promotion",
        "summary": "Suggesting use in a population or condition outside the approved labeling is a core enforcement theme.",
        "regulation": "21 CFR 202.1(e)(4)(i)(a); 21 CFR 201.128 / 801.4 (intended use)",
    },
    "unsupported_evidence": {
        "category": "Claims not supported by cited evidence",
        "summary": "Data presented (endpoints, percentages, populations) must match the cited source; selective or "
                   "misrepresented data is misleading.",
        "regulation": "21 CFR 202.1(e)(6)(iii)-(vii)",
    },
    "safety_minimization": {
        "category": "Minimization of safety signals",
        "summary": "Describing a product as 'safe' or 'well tolerated' without context while known serious risks exist.",
        "regulation": "21 CFR 202.1(e)(6)(iv)",
    },
    "device_claims": {
        "category": "Device claims beyond cleared / approved intended use",
        "summary": "Device promotion must stay within the 510(k) clearance / PMA intended use and labeling.",
        "regulation": "21 CFR 801.4; FD&C Act \u00a7502(q),(r)",
    },
}

CHECK_PRECEDENTS: Dict[str, List[str]] = {
    "safety_omission": ["risk_omission"],
    "fair_balance": ["fair_balance"],
    "absolute_claim": ["overstatement"],
    "comparative": ["superiority"],
    "off_label": ["off_label"],
    "population": ["off_label"],
    "unsupported": ["unsupported_evidence"],
    "no_evidence": ["unsupported_evidence"],
    "contradicted": ["safety_minimization", "risk_omission"],
    "safety_signal": ["safety_minimization"],
    "contraindication": ["risk_omission"],
    "cross_product": ["off_label", "device_claims"],
}


def precedents_for(check: str) -> List[Dict[str, str]]:
    return [{"key": k, **PRECEDENTS[k]} for k in CHECK_PRECEDENTS.get(check, [])]
