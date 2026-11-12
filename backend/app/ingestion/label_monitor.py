"""Label-change monitoring: version label sections, diff on refresh, and flag affected claims.

Each refresh records a SHA-256 per label section in ``label_versions``. A change to a critical section
(boxed warning, indications, contraindications) is a *critical* LabelChange for MLR teams.
"""
from __future__ import annotations

import difflib
from typing import Any, Dict, List, Optional

from app.core.db import OpsDB, sha256, utcnow

CRITICAL_SECTIONS = {"boxed_warning", "indications", "contraindications"}


def _summary(old: str, new: str, limit: int = 3) -> List[str]:
    old_s = [s.strip() for s in old.split(". ") if s.strip()]
    new_s = [s.strip() for s in new.split(". ") if s.strip()]
    out = []
    for line in difflib.unified_diff(old_s, new_s, lineterm="", n=0):
        if line.startswith(("+++", "---", "@@")):
            continue
        out.append(("ADDED: " if line.startswith("+") else "REMOVED: ") + line[1:][:220])
        if len(out) >= limit:
            break
    return out


def record_label(db: OpsDB, product_key: str, set_id: Optional[str], version: Optional[str], sections: Dict[str, str]) -> Dict[str, Any]:
    """Store the latest section hashes and return the diff against the previous observation."""
    previous: Dict[str, Dict[str, Any]] = {}
    for row in db.query("SELECT section, sha, text, version FROM label_versions WHERE product_key=? AND id IN "
                        "(SELECT MAX(id) FROM label_versions WHERE product_key=? GROUP BY section)", (product_key, product_key)):
        previous[row["section"]] = row
    first_observation = not previous
    changes: List[Dict[str, Any]] = []
    ts = utcnow()
    for section, text in sections.items():
        h = sha256(text)
        prev = previous.get(section)
        if prev and prev["sha"] == h:
            continue
        db.execute("INSERT INTO label_versions (ts, product_key, setid, version, section, sha, text) VALUES (?,?,?,?,?,?,?)",
                   (ts, product_key, set_id, version, section, h, text))
        if not first_observation:
            changes.append({"section": section, "change": "modified" if prev else "added", "critical": section in CRITICAL_SECTIONS,
                            "previous_version": prev["version"] if prev else None, "new_version": version,
                            "diff": _summary(prev["text"] if prev else "", text)})
    if not first_observation:
        for section, prev in previous.items():
            if section not in sections and prev["sha"] != sha256(""):
                db.execute("INSERT INTO label_versions (ts, product_key, setid, version, section, sha, text) VALUES (?,?,?,?,?,?,?)",
                           (ts, product_key, set_id, version, section, sha256(""), ""))
                changes.append({"section": section, "change": "removed", "critical": section in CRITICAL_SECTIONS,
                                "previous_version": prev["version"], "new_version": version, "diff": []})
    return {"first_observation": first_observation, "changes": changes,
            "critical": any(c["critical"] for c in changes)}


def affected_claims(db: OpsDB, product_id: str) -> List[Dict[str, Any]]:
    """Approved claims-library entries for the product that must be re-reviewed after a label change."""
    return db.query("SELECT text, claim_type, verdict, review_id FROM claims_library WHERE product_ids LIKE ? ORDER BY ts DESC LIMIT 25",
                    (f"%{product_id}%",))
