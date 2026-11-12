"""Entity resolution: brand / generic / SKU / misspelling -> graph node id.

Longest-alias-first exact matching on token boundaries, then fuzzy matching (difflib) for typos, following the
PharmaGraphRAG ``extract_entities`` and TruPharma RxNorm resolution patterns. Also provides fuzzy Kenvue detection so
misspelled consumer brands ("Tylenoll") cannot bypass the portfolio boundary.
"""
from __future__ import annotations

import difflib
import re
import threading
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from app.graph.seed_data import KENVUE_BRANDS, is_kenvue_brand
from app.models.schemas import NodeType

if TYPE_CHECKING:  # pragma: no cover
    from app.graph.graph_store import GraphStore

RESOLVABLE_TYPES = {NodeType.Product.value, NodeType.SoftwareModule.value, NodeType.Procedure.value}
GENERIC_WORDS = {"system", "module", "catheter", "intravascular", "robotic", "carto", "coronary", "primary", "protective", "silicone",
                 "surgical", "extended", "release", "tablets", "nasal", "spray", "solution", "total", "knee", "image", "mapping",
                 "integration", "segmentation", "guiding", "sheath", "generator", "drains", "with", "and", "plus", "the", "for"}
FUZZY_CUTOFF = 0.84


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text.lower())).strip()


class EntityResolver:
    def __init__(self, store: "GraphStore"):
        self.store = store
        self._version = -1
        self._lock = threading.Lock()
        self.alias_to_ids: Dict[str, List[str]] = {}
        self._single_aliases: List[str] = []

    def _aliases_for(self, nid: str, d: Dict) -> List[str]:
        name = d["name"]
        props = d.get("properties", {})
        out = {_norm(nid), _norm(name), _norm(name.split(" (")[0])}
        for part in re.split(r"\s*/\s*", name.split(" (")[0]):
            out.add(_norm(part))
        paren = re.findall(r"\(([^)]+)\)", name)
        for p in paren:
            if not re.search(r"\d|\band\b", p):
                out.add(_norm(p))
        if props.get("generic_name"):
            out.add(_norm(str(props["generic_name"])))
        if props.get("sku"):
            out.add(_norm(str(props["sku"])))
        for alias in props.get("aliases", []) or []:
            out.add(_norm(str(alias)))
        first = _norm(name).split(" ")[0] if name else ""
        if len(first) >= 5 and first not in GENERIC_WORDS:
            out.add(first)
        core = _norm(name.split(" (")[0]).split(" ")
        while len(core) > 1 and (core[-1] in GENERIC_WORDS or re.fullmatch(r"v\d+|version", core[-1])):
            core.pop()
        if len(" ".join(core)) >= 5:
            out.add(" ".join(core))
        return [a for a in out if a and len(a) >= 3 and a not in GENERIC_WORDS]

    def _ensure(self) -> None:
        if self._version == self.store.revision:
            return
        with self._lock:
            if self._version == self.store.revision:
                return
            index: Dict[str, List[str]] = {}
            for nid, d in self.store.graph.nodes(data=True):
                if d["label"] not in RESOLVABLE_TYPES:
                    continue
                for a in self._aliases_for(nid, d):
                    index.setdefault(a, [])
                    if nid not in index[a]:
                        index[a].append(nid)
            self.alias_to_ids = index
            self._single_aliases = [a for a in index if " " not in a and len(a) >= 5]
            self._version = self.store.revision

    def resolve(self, text: str) -> List[Dict[str, object]]:
        """Return entity hits ordered by match quality: exact (longest alias first), then fuzzy."""
        self._ensure()
        norm = f" {_norm(text)} "
        hits: Dict[str, Dict[str, object]] = {}
        consumed = norm
        for alias in sorted(self.alias_to_ids, key=len, reverse=True):
            needle = f" {alias} "
            if needle in consumed:
                for nid in self.alias_to_ids[alias]:
                    hits.setdefault(nid, {"id": nid, "alias": alias, "method": "exact", "score": 1.0})
                consumed = consumed.replace(needle, " # ")
        for tok in set(consumed.split()):
            if len(tok) < 5 or tok in GENERIC_WORDS or tok == "#":
                continue
            match = difflib.get_close_matches(tok, self._single_aliases, n=1, cutoff=FUZZY_CUTOFF)
            if match:
                score = difflib.SequenceMatcher(None, tok, match[0]).ratio()
                for nid in self.alias_to_ids[match[0]]:
                    hits.setdefault(nid, {"id": nid, "alias": match[0], "method": "fuzzy", "query_token": tok, "score": round(score, 3)})
        return sorted(hits.values(), key=lambda h: (h["method"] != "exact", -float(h["score"])))  # type: ignore[arg-type]

    def resolve_name(self, name: str) -> Optional[str]:
        hits = [h for h in self.resolve(name) if self.store.graph.nodes[h["id"]]["label"] != NodeType.Procedure.value]
        return str(hits[0]["id"]) if hits else None


def kenvue_mentions(text: str) -> List[str]:
    """Exact or misspelled Kenvue brand mentions (e.g. 'Tylenoll', 'Neutrogina')."""
    norm = f" {_norm(text)} "
    found = [b for b in KENVUE_BRANDS if f" {_norm(b)} " in norm]
    if is_kenvue_brand(text) and not found:
        found.append("Kenvue")
    # Fuzzy matching only for distinctive single-word brands; "Johnson" or "Clean" would collide with J&J itself.
    singles = {_norm(b): b for b in KENVUE_BRANDS if " " not in _norm(b)}
    for tok in set(norm.split()):
        if len(tok) < 5:
            continue
        m = difflib.get_close_matches(tok, list(singles), n=1, cutoff=0.8)
        if m and singles[m[0]] not in found:
            found.append(singles[m[0]])
    return found


_resolvers: Dict[int, EntityResolver] = {}


def get_resolver(store: "GraphStore") -> EntityResolver:
    r = _resolvers.get(id(store))
    if r is None or r.store is not store:
        r = EntityResolver(store)
        _resolvers.clear()
        _resolvers[id(store)] = r
    return r
