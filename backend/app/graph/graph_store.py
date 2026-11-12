"""Unified Neo4j + NetworkX MultiDiGraph adapter with Cypher MERGE generation.

NetworkX is always the in-process read model (fast traversal, zero setup) and is
persisted to ``backend/data/jnj_graph.json``. When ``NEO4J_URI`` is configured and
reachable, every upsert is mirrored to Neo4j via parameterized MERGE statements
and the in-memory model is hydrated from Neo4j at startup.
"""
from __future__ import annotations

import json
import logging
import threading
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import networkx as nx

from app.config import Settings, get_settings
from app.graph.seed_data import build_seed_graph, is_kenvue_brand
from app.models.schemas import BundleRequest, BundleResponse, EdgeType, GraphEdge, GraphNode, NodeType

logger = logging.getLogger(__name__)

NODE_COLORS: Dict[str, str] = {
    NodeType.BusinessUnit.value: "#D51900",
    NodeType.Franchise.value: "#F97316",
    NodeType.Product.value: "#22D3EE",
    NodeType.SoftwareModule.value: "#A78BFA",
    NodeType.Procedure.value: "#34D399",
    NodeType.Anatomy.value: "#F472B6",
    NodeType.ClinicalCondition.value: "#FBBF24",
    NodeType.EvidenceDocument.value: "#94A3B8",
    NodeType.BoxedWarning.value: "#EF4444",
    NodeType.HardwareCoupling.value: "#60A5FA",
}

# Hub nodes are never traversed *through* during ego expansion, otherwise every
# product would be within 2 hops of every other product in its business unit.
HUB_TYPES = {NodeType.BusinessUnit.value, NodeType.Franchise.value}


class KenvueBrandRejected(ValueError):
    """Raised when a Kenvue consumer-health brand is upserted into the graph."""


def cypher_merge_node(node: GraphNode) -> Tuple[str, Dict[str, Any]]:
    label = NodeType(node.label).value
    query = (
        f"MERGE (n:{label} {{id: $id}}) "
        "SET n.name = $name, n.division = $division, n.franchise = $franchise, n.properties_json = $props"
    )
    params = {
        "id": node.id,
        "name": node.name,
        "division": node.division,
        "franchise": node.franchise,
        "props": json.dumps(node.properties, default=str),
    }
    return query, params


def cypher_merge_edge(edge: GraphEdge) -> Tuple[str, Dict[str, Any]]:
    rel = EdgeType(edge.relation).value
    query = (
        "MATCH (a {id: $source}), (b {id: $target}) "
        f"MERGE (a)-[r:{rel}]->(b) SET r.properties_json = $props"
    )
    return query, {"source": edge.source, "target": edge.target, "props": json.dumps(edge.properties, default=str)}


class _Neo4jMirror:
    def __init__(self, settings: Settings):
        from neo4j import GraphDatabase  # imported lazily so offline mode never needs a driver

        self.database = settings.neo4j_database
        self.driver = GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))
        self.driver.verify_connectivity()

    def run(self, query: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        with self.driver.session(database=self.database) as session:
            return [r.data() for r in session.run(query, params)]

    def fetch_all(self) -> Tuple[List[GraphNode], List[GraphEdge]]:
        nodes: List[GraphNode] = []
        edges: List[GraphEdge] = []
        for rec in self.run("MATCH (n) WHERE n.id IS NOT NULL RETURN n, labels(n) AS labels", {}):
            n = rec["n"]
            label = next((l for l in rec["labels"] if l in NodeType.__members__), None)
            if not label:
                continue
            nodes.append(GraphNode(id=n["id"], label=label, name=n.get("name") or n["id"], division=n.get("division"),
                                   franchise=n.get("franchise"), properties=json.loads(n.get("properties_json") or "{}")))
        for rec in self.run("MATCH (a)-[r]->(b) RETURN a.id AS s, b.id AS t, type(r) AS rel, r.properties_json AS p", {}):
            if rec["rel"] in EdgeType.__members__:
                edges.append(GraphEdge(source=rec["s"], target=rec["t"], relation=rec["rel"], properties=json.loads(rec["p"] or "{}")))
        return nodes, edges

    def close(self) -> None:
        self.driver.close()


class GraphStore:
    def __init__(self, settings: Optional[Settings] = None, graph_path: Optional[Path] = None, use_neo4j: Optional[bool] = None):
        self.settings = settings or get_settings()
        self.graph_path = Path(graph_path or self.settings.graph_path)
        self.graph = nx.MultiDiGraph()
        self.revision = 0
        self._lock = threading.RLock()
        self.neo4j: Optional[_Neo4jMirror] = None
        self.backend_name = "networkx"
        want_neo4j = bool(self.settings.neo4j_uri) if use_neo4j is None else use_neo4j
        if want_neo4j and self.settings.neo4j_uri:
            try:
                self.neo4j = _Neo4jMirror(self.settings)
                self.backend_name = "neo4j+networkx"
                logger.info("Connected to Neo4j at %s", self.settings.neo4j_uri)
            except Exception as exc:  # pragma: no cover - depends on external server
                logger.warning("Neo4j unavailable (%s); falling back to NetworkX persistence", exc)
                self.neo4j = None

    # ------------------------------------------------------------------ lifecycle
    def initialize(self, force_reseed: bool = False) -> "GraphStore":
        """Load the graph from Neo4j / JSON, or seed the golden dataset when empty."""
        with self._lock:
            loaded = False
            if not force_reseed and self.neo4j is not None:
                nodes, edges = self.neo4j.fetch_all()
                if nodes:
                    self._load_objects(nodes, edges)
                    loaded = True
            if not loaded and not force_reseed and self.graph_path.exists():
                loaded = self.load()
            if not loaded or self.graph.number_of_nodes() == 0:
                self.seed()
            else:
                # Ensure golden-dataset entities always exist (idempotent upsert).
                self.seed(persist=False)
                self.save()
        return self

    def seed(self, persist: bool = True) -> None:
        nodes, edges = build_seed_graph()
        self.bulk_upsert(nodes, edges, persist=persist)

    def _load_objects(self, nodes: Iterable[GraphNode], edges: Iterable[GraphEdge]) -> None:
        for n in nodes:
            self._add_node_local(n)
        for e in edges:
            self._add_edge_local(e)

    def load(self) -> bool:
        try:
            payload = json.loads(self.graph_path.read_text(encoding="utf-8"))
            nodes = [GraphNode(**n) for n in payload.get("nodes", [])]
            edges = [GraphEdge(**e) for e in payload.get("edges", [])]
        except Exception as exc:
            logger.warning("Could not load %s (%s); reseeding", self.graph_path, exc)
            return False
        self.graph.clear()
        self._load_objects(nodes, edges)
        return True

    def save(self) -> None:
        with self._lock:
            payload = {
                "backend": self.backend_name,
                "nodes": [n.model_dump() for n in self.all_nodes()],
                "edges": [e.model_dump() for e in self.all_edges()],
            }
            self.graph_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.graph_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
            tmp.replace(self.graph_path)

    # ------------------------------------------------------------------ mutation
    def _add_node_local(self, node: GraphNode) -> None:
        self.revision += 1
        attrs = {"label": node.label, "name": node.name, "division": node.division, "franchise": node.franchise,
                 "properties": dict(node.properties)}
        if self.graph.has_node(node.id):
            existing = self.graph.nodes[node.id]
            merged_props = {**existing.get("properties", {}), **attrs["properties"]}
            existing.update(attrs)
            existing["properties"] = merged_props
        else:
            self.graph.add_node(node.id, **attrs)

    def _add_edge_local(self, edge: GraphEdge) -> bool:
        if not self.graph.has_node(edge.source) or not self.graph.has_node(edge.target):
            return False
        self.revision += 1
        if self.graph.has_edge(edge.source, edge.target, key=edge.relation):
            self.graph.edges[edge.source, edge.target, edge.relation]["properties"].update(edge.properties)
        else:
            self.graph.add_edge(edge.source, edge.target, key=edge.relation, relation=edge.relation, properties=dict(edge.properties))
        return True

    def upsert_node(self, node: GraphNode, persist: bool = False) -> GraphNode:
        if is_kenvue_brand(node.name) or is_kenvue_brand(node.id):
            raise KenvueBrandRejected(f"'{node.name}' is a Kenvue consumer-health brand and is outside the J&J portfolio")
        with self._lock:
            self._add_node_local(node)
            if self.neo4j is not None:
                self.neo4j.run(*cypher_merge_node(node))
            if persist:
                self.save()
        return node

    def upsert_edge(self, edge: GraphEdge, persist: bool = False) -> bool:
        with self._lock:
            ok = self._add_edge_local(edge)
            if ok and self.neo4j is not None:
                self.neo4j.run(*cypher_merge_edge(edge))
            if persist:
                self.save()
        return ok

    def bulk_upsert(self, nodes: Iterable[GraphNode], edges: Iterable[GraphEdge], persist: bool = True) -> Tuple[List[GraphNode], List[GraphEdge]]:
        added_nodes: List[GraphNode] = []
        added_edges: List[GraphEdge] = []
        with self._lock:
            for n in nodes:
                try:
                    added_nodes.append(self.upsert_node(n))
                except KenvueBrandRejected as exc:
                    logger.info("%s", exc)
            for e in edges:
                if self.upsert_edge(e):
                    added_edges.append(e)
            if persist:
                self.save()
        return added_nodes, added_edges

    def cypher_script(self) -> str:
        """Full idempotent Cypher MERGE script for exporting the graph into Neo4j."""
        lines: List[str] = []
        for n in self.all_nodes():
            q, p = cypher_merge_node(n)
            lines.append(f"// {p['id']}\n:param {json.dumps(p)}\n{q};")
        for e in self.all_edges():
            q, p = cypher_merge_edge(e)
            lines.append(f":param {json.dumps(p)}\n{q};")
        return "\n".join(lines)

    # ------------------------------------------------------------------ reads
    def has_node(self, node_id: str) -> bool:
        return self.graph.has_node(node_id)

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        if not self.graph.has_node(node_id):
            return None
        d = self.graph.nodes[node_id]
        return GraphNode(id=node_id, label=d["label"], name=d["name"], division=d.get("division"),
                         franchise=d.get("franchise"), properties=d.get("properties", {}))

    def node_dict(self, node_id: str) -> Dict[str, Any]:
        n = self.get_node(node_id)
        if n is None:
            return {}
        data = n.model_dump()
        data["color"] = NODE_COLORS.get(n.label, "#CBD5E1")
        data["degree"] = self.graph.degree(node_id)
        return data

    def all_nodes(self) -> List[GraphNode]:
        return [self.get_node(n) for n in self.graph.nodes]  # type: ignore[misc]

    def all_edges(self) -> List[GraphEdge]:
        return [GraphEdge(source=s, target=t, relation=d["relation"], properties=d.get("properties", {}))
                for s, t, d in self.graph.edges(data=True)]

    def out_edges(self, node_id: str, relation: Optional[str] = None) -> List[Tuple[str, str, Dict[str, Any]]]:
        return [(s, t, d) for s, t, d in self.graph.out_edges(node_id, data=True) if relation is None or d["relation"] == relation]

    def in_edges(self, node_id: str, relation: Optional[str] = None) -> List[Tuple[str, str, Dict[str, Any]]]:
        return [(s, t, d) for s, t, d in self.graph.in_edges(node_id, data=True) if relation is None or d["relation"] == relation]

    def neighbors(self, node_id: str) -> List[str]:
        return list(set(self.graph.successors(node_id)) | set(self.graph.predecessors(node_id)))

    def stats(self) -> Dict[str, Any]:
        labels = Counter(d["label"] for _, d in self.graph.nodes(data=True))
        divisions = Counter(d.get("division") or "Unassigned" for _, d in self.graph.nodes(data=True))
        sku_count = sum(1 for _, d in self.graph.nodes(data=True)
                        if d["label"] in (NodeType.Product.value, NodeType.SoftwareModule.value))
        return {
            "node_count": self.graph.number_of_nodes(),
            "edge_count": self.graph.number_of_edges(),
            "sku_count": sku_count,
            "franchise_count": labels.get(NodeType.Franchise.value, 0),
            "label_breakdown": dict(labels),
            "division_breakdown": dict(divisions),
        }

    def filtered_graph(self, division: Optional[str] = None, node_type: Optional[str] = None, search: Optional[str] = None) -> Dict[str, Any]:
        types = {t.strip() for t in node_type.split(",") if t.strip()} if node_type else None
        q = (search or "").strip().lower()
        keep = set()
        for nid, d in self.graph.nodes(data=True):
            if division and division.lower() not in ("all", "") and (d.get("division") or "") != division:
                continue
            if types and d["label"] not in types:
                continue
            if q:
                hay = " ".join([nid, d["name"], json.dumps(d.get("properties", {}), default=str)]).lower()
                if q not in hay:
                    continue
            keep.add(nid)
        nodes = [self.node_dict(n) for n in keep]
        links = [{"source": s, "target": t, "relation": d["relation"], "properties": d.get("properties", {})}
                 for s, t, d in self.graph.edges(data=True) if s in keep and t in keep]
        return {"nodes": sorted(nodes, key=lambda n: n["id"]), "links": links}

    # ------------------------------------------------------------------ delegated analytics
    def ego_subgraph(self, node_id: str, hops: int = 2) -> Dict[str, Any]:
        from app.graph.queries import ego_subgraph

        return ego_subgraph(self, node_id, hops)

    def compute_procedural_bundle(self, request: BundleRequest) -> BundleResponse:
        from app.graph.queries import compute_procedural_bundle

        return compute_procedural_bundle(self, request)

    def claim_lineage(self, node_id: str) -> Dict[str, Any]:
        from app.graph.queries import claim_lineage

        return claim_lineage(self, node_id)


_store: Optional[GraphStore] = None
_store_lock = threading.Lock()


def get_graph_store() -> GraphStore:
    global _store
    with _store_lock:
        if _store is None:
            _store = GraphStore().initialize()
        return _store


def set_graph_store(store: GraphStore) -> None:
    global _store
    with _store_lock:
        _store = store
