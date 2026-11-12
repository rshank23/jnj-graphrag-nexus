"""Model Context Protocol (MCP) server over stdio exposing the knowledge graph to Copilot / Claude / other agents.

Run:  python -m app.mcp_server
Speaks newline-delimited JSON-RPC 2.0 (MCP stdio transport): initialize, tools/list, tools/call, ping.
"""
from __future__ import annotations

import json
import sys
from typing import Any, Callable, Dict, Optional

from app.graph.graph_store import get_graph_store
from app.graph.seed_data import is_kenvue_brand
from app.models.schemas import AgentQueryRequest, BundleRequest

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "jnj-graphrag-nexus", "version": "1.1.0"}


def _graph_search(args: Dict[str, Any]) -> Any:
    query = str(args.get("query", "")).strip()
    if not query:
        raise ValueError("query is required")
    sub = get_graph_store().filtered_graph(search=query, division=args.get("division"))
    limit = int(args.get("limit", 15))
    return {"nodes": [{"id": n["id"], "label": n["label"], "name": n["name"], "division": n.get("division")} for n in sub["nodes"][:limit]],
            "total": len(sub["nodes"])}


def _ego(args: Dict[str, Any]) -> Any:
    store = get_graph_store()
    nid = args["node_id"]
    if not store.has_node(nid):
        raise ValueError(f"Node '{nid}' not found")
    sub = store.ego_subgraph(nid, int(args.get("hops", 1)))
    return {"center": nid, "nodes": [{"id": n["id"], "label": n["label"], "name": n["name"]} for n in sub["nodes"]],
            "edges": [{"source": e["source"], "target": e["target"], "relation": e["relation"]} for e in sub.get("links", sub.get("edges", []))]}


def _bundle(args: Dict[str, Any]) -> Any:
    req = BundleRequest(procedure_id=args["procedure_id"], annual_procedure_volume=int(args.get("annual_procedure_volume", 500)))
    return get_graph_store().compute_procedural_bundle(req).model_dump()


def _lineage(args: Dict[str, Any]) -> Any:
    return get_graph_store().claim_lineage(args["node_id"])


def _mlr(args: Dict[str, Any]) -> Any:
    from app.mlr.service import run_review

    r = run_review(get_graph_store(), args["text"], args.get("title") or "MCP asset", "mcp", use_llm=bool(args.get("use_llm", False)))
    return {"review_id": r["review_id"], "summary": r["summary"],
            "findings": [{k: f[k] for k in ("severity", "check", "title", "detail", "suggestion")} for f in r["findings"]]}


def _agent(args: Dict[str, Any]) -> Any:
    from app.agents.supervisor import get_supervisor

    query = args["query"]
    if is_kenvue_brand(query):
        raise ValueError("Kenvue consumer-health brands are outside the J&J portfolio")
    res = get_supervisor(get_graph_store()).run(AgentQueryRequest(query=query), role=args.get("role"), actor="mcp")
    return {"answer": res.answer_markdown, "agent": res.routed_agent, "confidence": res.confidence, "risk_level": res.risk_level,
            "citations": res.citations}


def _obj(props: Dict[str, Any], required: list) -> Dict[str, Any]:
    return {"type": "object", "properties": props, "required": required}


TOOLS: Dict[str, Dict[str, Any]] = {
    "graph_search": {"fn": _graph_search, "description": "Search J&J products, procedures, conditions and evidence by name/text.",
                     "schema": _obj({"query": {"type": "string"}, "division": {"type": "string", "enum": ["Innovative Medicine", "MedTech"]},
                                     "limit": {"type": "integer", "default": 15}}, ["query"])},
    "ego_subgraph": {"fn": _ego, "description": "Return the k-hop neighbourhood (nodes + typed edges) around a node id.",
                     "schema": _obj({"node_id": {"type": "string"}, "hops": {"type": "integer", "default": 1}}, ["node_id"])},
    "procedural_bundle": {"fn": _bundle, "description": "Compute the MedTech procedural bundle and cross-sell value for a procedure.",
                          "schema": _obj({"procedure_id": {"type": "string"}, "annual_procedure_volume": {"type": "integer"}}, ["procedure_id"])},
    "claim_lineage": {"fn": _lineage, "description": "Trace a product's claims back to their evidence documents.",
                      "schema": _obj({"node_id": {"type": "string"}}, ["node_id"])},
    "mlr_review": {"fn": _mlr, "description": "Run the MLR pre-review copilot over promotional copy; returns findings with severity.",
                   "schema": _obj({"text": {"type": "string"}, "title": {"type": "string"}, "use_llm": {"type": "boolean"}}, ["text"])},
    "agent_query": {"fn": _agent, "description": "Ask the GraphRAG multi-agent supervisor a question; returns a cited answer.",
                    "schema": _obj({"query": {"type": "string"}, "role": {"type": "string", "enum": ["commercial", "medical", "mlr", "admin"]}},
                                   ["query"])},
}


def _ok(rid: Any, result: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def _err(rid: Any, code: int, message: str) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


def handle(request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Handle one JSON-RPC message; returns None for notifications."""
    rid, method, params = request.get("id"), request.get("method"), request.get("params") or {}
    if rid is None and method and method.startswith("notifications/"):
        return None
    if method == "initialize":
        return _ok(rid, {"protocolVersion": PROTOCOL_VERSION, "capabilities": {"tools": {"listChanged": False}}, "serverInfo": SERVER_INFO})
    if method == "ping":
        return _ok(rid, {})
    if method == "tools/list":
        return _ok(rid, {"tools": [{"name": n, "description": t["description"], "inputSchema": t["schema"]} for n, t in TOOLS.items()]})
    if method == "tools/call":
        tool = TOOLS.get(params.get("name"))
        if tool is None:
            return _err(rid, -32602, f"Unknown tool '{params.get('name')}'")
        fn: Callable[[Dict[str, Any]], Any] = tool["fn"]
        try:
            result = fn(params.get("arguments") or {})
            return _ok(rid, {"content": [{"type": "text", "text": json.dumps(result, default=str)}], "isError": False})
        except Exception as exc:
            return _ok(rid, {"content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"}], "isError": True})
    return _err(rid, -32601, f"Method not found: {method}")


def main() -> None:  # pragma: no cover - stdio loop
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            resp = handle(json.loads(line))
        except json.JSONDecodeError:
            resp = _err(None, -32700, "Parse error")
        if resp is not None:
            sys.stdout.write(json.dumps(resp, default=str) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":  # pragma: no cover
    main()
