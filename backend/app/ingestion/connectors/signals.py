"""Pharmacovigilance disproportionality statistics (PRR / ROR with 95% CI) from FAERS-style 2x2 tables.

                    reaction R   other reactions
    drug D              a              b
    other drugs         c              d

Signal criteria follow Evans et al. (2001): PRR >= 2, chi-square >= 4 and a >= 3, plus ROR lower 95% CI > 1.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Dict


@dataclass
class Disproportionality:
    a: int
    b: int
    c: int
    d: int
    prr: float
    prr_ci_low: float
    prr_ci_high: float
    ror: float
    ror_ci_low: float
    ror_ci_high: float
    chi_square: float
    is_signal: bool

    def to_dict(self) -> Dict[str, Any]:
        return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in asdict(self).items()}


def contingency_from_totals(drug_reaction: int, drug_total: int, reaction_total: int, all_total: int) -> tuple[int, int, int, int]:
    a = max(0, drug_reaction)
    b = max(0, drug_total - a)
    c = max(0, reaction_total - a)
    d = max(0, all_total - a - b - c)
    return a, b, c, d


def disproportionality(a: int, b: int, c: int, d: int) -> Disproportionality:
    # Haldane-Anscombe 0.5 correction keeps the statistics defined when a cell is zero.
    ac, bc, cc, dc = (x + 0.5 for x in (a, b, c, d)) if 0 in (a, b, c, d) else (float(a), float(b), float(c), float(d))
    prr = (ac / (ac + bc)) / (cc / (cc + dc))
    se_prr = math.sqrt(1 / ac - 1 / (ac + bc) + 1 / cc - 1 / (cc + dc))
    ror = (ac * dc) / (bc * cc)
    se_ror = math.sqrt(1 / ac + 1 / bc + 1 / cc + 1 / dc)
    n = a + b + c + d
    denom = (a + b) * (c + d) * (a + c) * (b + d)
    chi = (n * (abs(a * d - b * c) - n / 2) ** 2 / denom) if denom else 0.0
    ror_lo = math.exp(math.log(ror) - 1.96 * se_ror)
    return Disproportionality(
        a=a, b=b, c=c, d=d,
        prr=prr, prr_ci_low=math.exp(math.log(prr) - 1.96 * se_prr), prr_ci_high=math.exp(math.log(prr) + 1.96 * se_prr),
        ror=ror, ror_ci_low=ror_lo, ror_ci_high=math.exp(math.log(ror) + 1.96 * se_ror),
        chi_square=chi, is_signal=bool(prr >= 2.0 and chi >= 4.0 and a >= 3 and ror_lo > 1.0),
    )
