"""Graph analytics: 2-hop ego subgraphs, MedTech BOM cross-sell calculator, claim lineage."""
from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from app.models.schemas import BundleItem, BundleRequest, BundleResponse, EdgeType, NodeType

if TYPE_CHECKING:  # pragma: no cover
    from app.graph.graph_store import GraphStore


def serialize_path_edge(store: "GraphStore", source: str, relation: str, target: str) -> str:
    s = store.graph.nodes[source]["name"]
    t = store.graph.nodes[target]["name"]
    return f"({s}) -[{relation}]-> ({t})"


def ego_subgraph(store: "GraphStore", node_id: str, hops: int = 2) -> Dict[str, Any]:
    """Undirected BFS ego network. Hub nodes (BusinessUnit/Franchise) are included but not expanded through."""
    from app.graph.graph_store import HUB_TYPES

    if not store.has_node(node_id):
        raise KeyError(node_id)
    distance: Dict[str, int] = {node_id: 0}
    queue: deque[str] = deque([node_id])
    while queue:
        current = queue.popleft()
        d = distance[current]
        if d >= hops:
            continue
        if current != node_id and store.graph.nodes[current]["label"] in HUB_TYPES:
            continue
        for nb in store.neighbors(current):
            if nb not in distance:
                distance[nb] = d + 1
                queue.append(nb)

    keep = set(distance)
    nodes = []
    for nid in keep:
        nd = store.node_dict(nid)
        nd["hop"] = distance[nid]
        nodes.append(nd)
    links: List[Dict[str, Any]] = []
    paths: List[str] = []
    for s, t, data in store.graph.edges(data=True):
        if s in keep and t in keep:
            # Only keep edges that lie on a BFS frontier (|hop diff| <= 1) to avoid hub cross-talk.
            if abs(distance[s] - distance[t]) <= 1:
                links.append({"source": s, "target": t, "relation": data["relation"], "properties": data.get("properties", {})})
                paths.append(serialize_path_edge(store, s, data["relation"], t))
    nodes.sort(key=lambda n: (n["hop"], n["label"], n["name"]))
    return {
        "center": store.node_dict(node_id),
        "hops": hops,
        "nodes": nodes,
        "links": links,
        "paths": paths,
        "one_hop": [n["id"] for n in nodes if n["hop"] == 1],
        "two_hop": [n["id"] for n in nodes if n["hop"] == 2],
        "claims": claim_lineage(store, node_id)["claims"],
    }


_ROLE_BY_RELATION = {
    EdgeType.PRIMARY_PLATFORM_FOR.value: "Capital navigation / robotic platform",
    EdgeType.INTEGRATES_WITH.value: "Software module integrated with capital platform",
    EdgeType.COMPATIBLE_ACCESSORY.value: "Intra-operative accessory compatible with platform",
    EdgeType.GUIDES_TRANSSEPTAL_PUNCTURE.value: "Intracardiac echo guidance for transseptal puncture",
    EdgeType.INDICATED_FOR.value: "Procedural device / implant",
    EdgeType.POST_OP_INFECTION_CONTROL_FOR.value: "Post-operative infection control",
    EdgeType.POST_OP_DRAINAGE_FOR.value: "Post-operative closed wound drainage",
}


def _first_evidence(store: "GraphStore", node_id: str) -> Optional[str]:
    ev = store.out_edges(node_id, EdgeType.SUPPORTED_BY_EVIDENCE.value)
    return ev[0][1] if ev else None


def _bundle_item(store: "GraphStore", node_id: str, relation: str) -> BundleItem:
    n = store.get_node(node_id)
    assert n is not None
    p = n.properties
    return BundleItem(
        id=n.id,
        name=n.name,
        category=p.get("category", n.label),
        role_in_procedure=_ROLE_BY_RELATION.get(relation, relation),
        unit_price_usd=float(p.get("price_usd", 0.0)),
        is_capital_equipment=bool(p.get("is_capital_equipment", False)),
        clinical_claim=p.get("clinical_claim"),
        evidence_doc_id=_first_evidence(store, n.id),
    )


def compute_procedural_bundle(store: "GraphStore", request: BundleRequest) -> BundleResponse:
    """Traverse the procedure ecosystem into a 4-tier Bill-of-Materials and compute deal economics.

    Financial model:
      baseline_capital            = sum(capital platforms) + sum(software modules)   (one-time)
      per_procedure_consumables   = sum(tier-3 catheters/sheaths/implants) + sum(tier-4 Ethicon post-op)
      annual_consumable_cross_sell= per_procedure_consumables * annual_volume
      total_first_year_deal_value = baseline_capital + annual_consumable_cross_sell
      attachment_uplift_pct       = annual_consumable_cross_sell / baseline_capital * 100
    """
    proc = store.get_node(request.procedure_id)
    if proc is None or proc.label != NodeType.Procedure.value:
        raise KeyError(request.procedure_id)

    seen: set[str] = set()

    def take(pairs: List[Tuple[str, str]], predicate=lambda n: True) -> List[BundleItem]:
        items: List[BundleItem] = []
        for nid, rel in pairs:
            if nid in seen:
                continue
            node = store.get_node(nid)
            if node is None or not predicate(node):
                continue
            seen.add(nid)
            items.append(_bundle_item(store, nid, rel))
        return items

    platform_pairs = [(s, d["relation"]) for s, _, d in store.in_edges(proc.id, EdgeType.PRIMARY_PLATFORM_FOR.value)]
    capital = take(platform_pairs, lambda n: bool(n.properties.get("is_capital_equipment")))

    software_pairs: List[Tuple[str, str]] = []
    accessory_pairs: List[Tuple[str, str]] = []
    for platform in capital:
        software_pairs += [(s, d["relation"]) for s, _, d in store.in_edges(platform.id, EdgeType.INTEGRATES_WITH.value)]
        accessory_pairs += [(s, d["relation"]) for s, _, d in store.in_edges(platform.id, EdgeType.COMPATIBLE_ACCESSORY.value)]
    software = take(software_pairs, lambda n: n.label == NodeType.SoftwareModule.value)

    accessory_pairs += [(s, d["relation"]) for s, _, d in store.in_edges(proc.id, EdgeType.GUIDES_TRANSSEPTAL_PUNCTURE.value)]
    accessory_pairs += [(s, d["relation"]) for s, _, d in store.in_edges(proc.id, EdgeType.INDICATED_FOR.value)]
    procedural = take(accessory_pairs, lambda n: n.label == NodeType.Product.value and not n.properties.get("is_capital_equipment"))

    post_op: List[BundleItem] = []
    if request.include_post_op_consumables:
        post_pairs = [(s, d["relation"]) for s, _, d in store.in_edges(proc.id, EdgeType.POST_OP_INFECTION_CONTROL_FOR.value)]
        post_pairs += [(s, d["relation"]) for s, _, d in store.in_edges(proc.id, EdgeType.POST_OP_DRAINAGE_FOR.value)]
        post_op = take(post_pairs, lambda n: n.label == NodeType.Product.value)

    baseline = sum(i.unit_price_usd for i in capital + software)
    per_proc = sum(i.unit_price_usd for i in procedural + post_op)
    annual = per_proc * request.annual_procedure_volume
    total = baseline + annual
    uplift = (annual / baseline * 100.0) if baseline > 0 else 0.0

    return BundleResponse(
        procedure_id=proc.id,
        procedure_name=proc.name,
        annual_volume=request.annual_procedure_volume,
        capital_platforms=capital,
        software_modules=software,
        procedural_catheters_and_sheaths=procedural,
        post_op_ethicon_consumables=post_op,
        baseline_capital_revenue_usd=round(baseline, 2),
        per_procedure_consumable_revenue_usd=round(per_proc, 2),
        annual_consumable_cross_sell_usd=round(annual, 2),
        total_first_year_deal_value_usd=round(total, 2),
        attachment_uplift_pct=round(uplift, 2),
    )


def claim_lineage(store: "GraphStore", node_id: str) -> Dict[str, Any]:
    """Trace every claim on a node to its EvidenceDocument / BoxedWarning provenance."""
    node = store.get_node(node_id)
    if node is None:
        raise KeyError(node_id)
    p = node.properties
    claims: List[Dict[str, Any]] = []
    for key in ("clinical_claim", "indication", "mechanism", "trial_data", "contraindication"):
        if p.get(key):
            claims.append({"type": key, "text": p[key]})

    evidence: List[Dict[str, Any]] = []
    paths: List[str] = []
    for _, doc, d in store.out_edges(node_id, EdgeType.SUPPORTED_BY_EVIDENCE.value):
        evidence.append(store.node_dict(doc))
        paths.append(serialize_path_edge(store, node_id, d["relation"], doc))

    warnings: List[Dict[str, Any]] = []
    for _, bw, d in store.out_edges(node_id, EdgeType.HAS_BOXED_WARNING.value):
        warnings.append(store.node_dict(bw))
        paths.append(serialize_path_edge(store, node_id, d["relation"], bw))
        for _, doc, d2 in store.out_edges(bw, EdgeType.SUPPORTED_BY_EVIDENCE.value):
            if all(e["id"] != doc for e in evidence):
                evidence.append(store.node_dict(doc))
            paths.append(serialize_path_edge(store, bw, d2["relation"], doc))
    if p.get("boxed_warning"):
        claims.append({"type": "boxed_warning", "text": p["boxed_warning"]})

    contraindications: List[Dict[str, Any]] = []
    for _, c, d in store.out_edges(node_id, EdgeType.CONTRAINDICATED_WITH.value):
        contraindications.append({**store.node_dict(c), "severity": d.get("properties", {}).get("severity")})
        paths.append(serialize_path_edge(store, node_id, d["relation"], c))

    return {
        "node": store.node_dict(node_id),
        "claims": claims,
        "evidence_documents": evidence,
        "boxed_warnings": warnings,
        "contraindications": contraindications,
        "lineage_paths": paths,
        "provenance_status": "verified" if evidence else "unverified - no linked EvidenceDocument",
    }
