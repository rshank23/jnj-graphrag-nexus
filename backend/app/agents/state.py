"""LangGraph TypedDict state for the J&J multi-agent supervisor."""
from __future__ import annotations

import operator
from typing import Optional, Annotated, Any, Dict, List, TypedDict


class AgentState(TypedDict, total=False):
    query: str
    max_hops: int
    top_k: int
    routed_agent: str
    route_scores: Dict[str, float]
    route_reason: str
    retrieval: Dict[str, Any]
    focus_node_ids: List[str]
    agent_markdown: str
    agent_payload: Dict[str, Any]
    agent_subgraph: Dict[str, Any]
    citations: List[Dict[str, Any]]
    answer_markdown: str
    subgraph: Dict[str, Any]
    reranked_passages: List[Dict[str, Any]]
    llm: Optional[Dict[str, Any]]
    execution_trace: Annotated[List[str], operator.add]
