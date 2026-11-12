"""LangGraph Supervisor routing across three specialized J&J domain agents."""
from __future__ import annotations

import logging
import re
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import httpx
from langgraph.graph import END, StateGraph

from app.agents.state import AgentState
from app.config import get_settings
from app.graph.graph_store import HUB_TYPES, NODE_COLORS
from app.graph.seed_data import IM, MT
from app.models.schemas import AgentQueryRequest, AgentQueryResponse, BundleRequest, EdgeType, NodeType
from app.rag.hybrid_retriever import HybridGraphRetriever, get_retriever

if TYPE_CHECKING:  # pragma: no cover
    from app.graph.graph_store import GraphStore

logger = logging.getLogger(__name__)

MEDTECH = "medtech_bundler_agent"
PHARMA = "pharma_clinical_agent"
REGULATORY = "regulatory_auditor_agent"
AGENT_LABELS = {MEDTECH: "medtech_bundler", PHARMA: "pharma_clinical", REGULATORY: "regulatory_auditor"}

ROUTING_KEYWORDS: Dict[str, List[Tuple[str, float]]] = {
    MEDTECH: [
        (r"\bprocedur", 2), (r"\bablation\b", 2), (r"\bcarto", 2), (r"\b3d\s*ct\b", 2), (r"\bsegment", 1.5), (r"\bvelys\b", 2),
        (r"\bknee\b|\btka\b|\barthroplasty\b", 2), (r"cross[\s-]*sell", 3), (r"\bbundle\b|\bbill[\s-]*of[\s-]*materials\b|\bbom\b", 3),
        (r"\bhospital\b|\bquote\b|\bdeal\b|\broi\b", 2), (r"\bethicon\b", 2), (r"\bconsumable", 2), (r"\bcatheter|\bsheath", 1.5),
        (r"saw\s*blade|\bcoupling", 2.5), (r"\bbiopatch\b|\bblake\b|\bmonocryl\b", 1.5), (r"\bivl\b|\blithotripsy\b|\bshockwave\b|\bpci\b", 2),
        (r"\bmedtech\b", 1.5), (r"\bsoftware module", 2), (r"\batrial fibrillation\b|\bafib\b", 2), (r"\bcompatib", 1.5),
    ],
    PHARMA: [
        (r"\boncology\b|\bimmunology\b|\bneuroscience\b", 2), (r"\bpah\b|pulmonary arterial hypertension", 2.5), (r"\bdrugs?\b|\bmedicines?\b|\btherap", 1.5),
        (r"\bmechanism", 2), (r"\bsynerg", 3), (r"\bpathway", 3), (r"work(?:s)? together|\bcombination", 2.5), (r"boxed warning", 2),
        (r"\bindication|\bindicated\b", 1), (r"\bmyeloma\b|\bpsoriasis\b|\bdepression\b|\bschizophrenia\b|\bcancer\b|\bnsclc\b", 1.5),
        (r"\binnovative medicine\b", 1.5), (r"\bclinical brief\b|\bclinical affairs\b", 2),
    ],
    REGULATORY: [
        (r"\baudit", 4), (r"\bfda\b", 2), (r"\bspl\b|\bdailymed\b", 2.5), (r"\bprovenance\b|\blineage\b", 4), (r"\bwindchill\b", 4),
        (r"\bclaims?\b", 2), (r"\bcontraindicat", 1.5), (r"\blabel\b|\bprescribing information\b", 1.5), (r"\bcitation|\bevidence\b", 1.5),
        (r"trial data|\bcompliance\b|\bregulatory\b", 2), (r"\befficacy\b", 1),
    ],
}
PROCEDURE_KEYWORDS = [
    ("PROC_AFIB_ABLATION", r"atrial fibrillation|\bafib\b|\bablation\b|\bcarto\b|\belectrophysiolog|cardiac anatomy|3d\s*ct"),
    ("PROC_TKA_ROBOTIC", r"\bknee\b|\btka\b|arthroplasty|\bvelys\b|\battune\b|saw blade"),
    ("PROC_CALCIFIED_PCI", r"\bpci\b|\bivl\b|lithotripsy|calcified|\bcoronary\b|\bshockwave\b|\bjavelin\b"),
]


def route_query(query: str, retrieval: Optional[Dict[str, Any]] = None, store: Optional["GraphStore"] = None) -> Tuple[str, Dict[str, float], str]:
    q = query.lower()
    scores: Dict[str, float] = {}
    for agent, rules in ROUTING_KEYWORDS.items():
        scores[agent] = sum(w for pat, w in rules if re.search(pat, q))
    if store is not None and retrieval is not None:
        for nid in retrieval.get("entity_mentions", [])[:6]:
            div = store.graph.nodes[nid].get("division")
            scores[PHARMA if div == IM else MEDTECH] += 1.0
    best = max(scores.values())
    if best == 0:
        top_div = None
        if store is not None and retrieval and retrieval.get("seeds"):
            top_div = store.graph.nodes[retrieval["seeds"][0]].get("division")
        agent = PHARMA if top_div == IM else MEDTECH
        reason = f"No explicit domain keywords; routed by top retrieved entity division ({top_div or 'unknown'})."
    else:
        priority = [REGULATORY, PHARMA, MEDTECH]
        agent = next(a for a in priority if scores[a] == best)
        reason = f"Highest domain intent score {best:.1f} for {AGENT_LABELS[agent]}."
    return agent, {AGENT_LABELS[a]: round(s, 2) for a, s in scores.items()}, reason


def _usd(v: float) -> str:
    return f"${v:,.0f}"


def _cell(text: Optional[str], limit: int = 140) -> str:
    if not text:
        return "-"
    text = text.replace("|", "/").replace("\n", " ")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _focus_nodes(store: "GraphStore", retrieval: Dict[str, Any], division: Optional[str], types: set, limit: int = 4) -> List[str]:
    out: List[str] = []
    for nid in retrieval.get("entity_mentions", []) + retrieval.get("seeds", []) + [p["id"] for p in retrieval.get("reranked_passages", []) if p["type"] == "passage"]:
        d = store.graph.nodes.get(nid)
        if not d or d["label"] not in types or nid in out:
            continue
        if division and d.get("division") != division:
            continue
        out.append(nid)
    mentioned = [n for n in retrieval.get("entity_mentions", []) if n in out]
    return mentioned[:6] if mentioned else out[:limit]


def _subgraph_for(store: "GraphStore", node_ids: List[str], hops: int = 1) -> Dict[str, Any]:
    nodes: Dict[str, Dict[str, Any]] = {}
    links: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for nid in node_ids:
        if not store.has_node(nid):
            continue
        ego = store.ego_subgraph(nid, hops)
        for n in ego["nodes"]:
            nodes.setdefault(n["id"], n)
        for l in ego["links"]:
            links.setdefault((l["source"], l["target"], l["relation"]), l)
    return {"nodes": list(nodes.values()), "links": list(links.values())}


def _merge_subgraphs(*graphs: Dict[str, Any]) -> Dict[str, Any]:
    nodes: Dict[str, Dict[str, Any]] = {}
    links: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for g in graphs:
        for n in g.get("nodes", []):
            nodes.setdefault(n["id"], n)
        for l in g.get("links", []):
            links.setdefault((l["source"], l["target"], l["relation"]), l)
    return {"nodes": list(nodes.values()), "links": [l for l in links.values() if l["source"] in nodes and l["target"] in nodes]}


def _citation(store: "GraphStore", doc_id: str) -> Dict[str, Any]:
    d = store.graph.nodes[doc_id]
    p = d.get("properties", {})
    return {"id": doc_id, "title": d["name"], "doc_type": p.get("doc_type"), "source_url": p.get("source_url"),
            "published": p.get("published"), "windchill_id": p.get("windchill_id")}


def _evidence_for(store: "GraphStore", node_id: str) -> List[str]:
    docs = [t for _, t, _ in store.out_edges(node_id, EdgeType.SUPPORTED_BY_EVIDENCE.value)]
    for _, bw, _ in store.out_edges(node_id, EdgeType.HAS_BOXED_WARNING.value):
        docs += [t for _, t, _ in store.out_edges(bw, EdgeType.SUPPORTED_BY_EVIDENCE.value)]
    return list(dict.fromkeys(docs))


class SupervisorRunner:
    def __init__(self, store: "GraphStore", retriever: Optional[HybridGraphRetriever] = None):
        self.store = store
        self.retriever = retriever or get_retriever(store)
        self.graph = self._build()

    # ------------------------------------------------------------------ nodes
    def supervisor_router(self, state: AgentState) -> Dict[str, Any]:
        retrieval = self.retriever.retrieve(state["query"], top_k=state.get("top_k", 5), max_hops=state.get("max_hops", 2))
        agent, scores, reason = route_query(state["query"], retrieval, self.store)
        t = retrieval["timings_ms"]
        m = retrieval["methods"]
        trace = [
            f"Supervisor Router: intent scores {scores} -> {AGENT_LABELS[agent]} ({reason})",
            f"Hybrid BM25+Vector Search: {m['lexical']} + {m['dense']} fused via {m['fusion']} "
            f"({len(retrieval['rrf_top'])} fused hits, seeds={retrieval['seeds']}, {t['hybrid_search']} ms)",
            f"2-Hop Graph Expansion: {len(retrieval['subgraph']['nodes'])} nodes / {len(retrieval['subgraph']['links'])} edges "
            f"from {len(retrieval['seeds'])} seed entities ({t['graph_expansion']} ms)",
            f"Cross-Encoder Reranker: {m['reranker']} scored passages + serialized graph paths, kept "
            f"{len(retrieval['reranked_passages'])} ({t['rerank']} ms)",
        ]
        return {"retrieval": retrieval, "routed_agent": agent, "route_scores": scores, "route_reason": reason, "execution_trace": trace}

    def medtech_bundler_agent(self, state: AgentState) -> Dict[str, Any]:
        q = state["query"].lower()
        retrieval = state["retrieval"]
        procedures = [pid for pid, pat in PROCEDURE_KEYWORDS if re.search(pat, q)]
        if not procedures:
            procedures = [n["id"] for n in retrieval["subgraph"]["nodes"] if n["label"] == NodeType.Procedure.value][:1]
        if not procedures:
            procedures = ["PROC_AFIB_ABLATION"]
        vol_match = re.search(r"(\d[\d,]{1,6})\s*(?:procedures|cases|annual|per year|/yr)", q)
        volume = int(vol_match.group(1).replace(",", "")) if vol_match else 500
        include_post_op = not re.search(r"without (?:post[\s-]*op|ethicon)|exclude post", q)

        md: List[str] = ["## J&J MedTech Procedural Bundle & Compatibility Analysis"]
        bundles: List[Dict[str, Any]] = []
        focus: List[str] = []
        citations: Dict[str, Dict[str, Any]] = {}
        for pid in procedures[:2]:
            b = self.store.compute_procedural_bundle(BundleRequest(procedure_id=pid, annual_procedure_volume=volume,
                                                                   include_post_op_consumables=include_post_op))
            bundles.append(b.model_dump())
            focus.append(pid)
            md.append(f"\n### {b.procedure_name} — {volume:,} procedures/year\n")
            md.append("| Tier | Item | SKU | Role | Unit Price | Evidence |")
            md.append("|---|---|---|---|---|---|")
            tiers = [("1 · Capital Platform", b.capital_platforms), ("2 · 3D CT/MRI Software", b.software_modules),
                     ("3 · Catheters/Sheaths/Implants", b.procedural_catheters_and_sheaths),
                     ("4 · Ethicon Post-Op", b.post_op_ethicon_consumables)]
            for tier, items in tiers:
                for it in items:
                    sku = self.store.graph.nodes[it.id]["properties"].get("sku", "-")
                    price = _usd(it.unit_price_usd) + ("" if it.is_capital_equipment else "/proc")
                    md.append(f"| {tier} | **{it.name}** | `{sku}` | {_cell(it.role_in_procedure, 60)} | {price} | {it.evidence_doc_id or '-'} |")
                    focus.append(it.id)
                    if it.evidence_doc_id:
                        citations[it.evidence_doc_id] = _citation(self.store, it.evidence_doc_id)
            md.append("\n**Deal economics**\n")
            md.append(f"- Baseline capital deal (platform + software): **{_usd(b.baseline_capital_revenue_usd)}**")
            md.append(f"- Per-procedure consumable cross-sell: **{_usd(b.per_procedure_consumable_revenue_usd)}**")
            md.append(f"- Annual recurring consumable uplift: **{_usd(b.annual_consumable_cross_sell_usd)}**")
            md.append(f"- Total first-year deal value: **{_usd(b.total_first_year_deal_value_usd)}**")
            md.append(f"- Attachment uplift vs. capital: **{b.attachment_uplift_pct:,.1f}%**")

        compat_lines: List[str] = []
        wants_ct = re.search(r"3d\s*ct|segment|anatomy|imaging", q)
        wants_coupling = re.search(r"saw\s*blade|coupling|competitor|cross[\s-]*compatib", q)
        if wants_ct:
            for s, t, d in self.store.graph.edges(data=True):
                if d["relation"] == EdgeType.AUTO_SEGMENTS_3D_CT.value:
                    compat_lines.append(f"- **{self.store.graph.nodes[s]['name']}** -[AUTO_SEGMENTS_3D_CT]-> {self.store.graph.nodes[t]['name']}")
                    focus += [s, t]
        if wants_coupling:
            for s, t, d in self.store.graph.edges(data=True):
                if d["relation"] == EdgeType.COMPATIBLE_COUPLING.value:
                    compat_lines.append(f"- **{self.store.graph.nodes[s]['name']}** -[COMPATIBLE_COUPLING]-> {self.store.graph.nodes[t]['name']}")
                    focus += [s, t]
                    for doc in _evidence_for(self.store, s):
                        citations[doc] = _citation(self.store, doc)
        if compat_lines:
            md.append("\n### Graph Compatibility Findings\n")
            md.extend(compat_lines)
        focus = list(dict.fromkeys(focus))
        return {
            "agent_markdown": "\n".join(md),
            "agent_payload": {"bundles": bundles},
            "focus_node_ids": focus,
            "agent_subgraph": _subgraph_for(self.store, procedures[:2], hops=2),
            "citations": list(citations.values()),
            "execution_trace": [f"Domain Sub-Agent (medtech_bundler): GraphStore.compute_procedural_bundle({', '.join(procedures[:2])}) "
                                f"at {volume} procedures/year; {len(compat_lines)} compatibility edges surfaced"],
        }

    def pharma_clinical_agent(self, state: AgentState) -> Dict[str, Any]:
        retrieval = state["retrieval"]
        focus = _focus_nodes(self.store, retrieval, IM, {NodeType.Product.value}, limit=4)
        md: List[str] = ["## J&J Innovative Medicine Clinical Affairs Brief"]
        citations: Dict[str, Dict[str, Any]] = {}
        synergy: List[str] = []
        contra: List[str] = []
        for pid in focus:
            n = self.store.get_node(pid)
            assert n is not None
            p = n.properties
            md.append(f"\n### {n.name}\n")
            md.append(f"- **Franchise:** {n.franchise or '-'}")
            md.append(f"- **Mechanism of action:** {p.get('mechanism', '-')}")
            if p.get("pathway"):
                md.append(f"- **Biological pathway:** {p['pathway']}")
            conds = [self.store.graph.nodes[t]["name"] for _, t, _ in self.store.out_edges(pid, EdgeType.INDICATED_FOR.value)]
            md.append(f"- **Indication:** {p.get('indication', '-')}")
            if conds:
                md.append(f"- **Graph-linked conditions:** {', '.join(conds)}")
            if p.get("trial_data"):
                md.append(f"- **Trial data:** {p['trial_data']}")
            for _, bw, _ in self.store.out_edges(pid, EdgeType.HAS_BOXED_WARNING.value):
                md.append(f"- ⚠️ **BOXED WARNING:** {self.store.graph.nodes[bw]['properties'].get('warning_text')}")
            for s, t, d in self.store.out_edges(pid, EdgeType.SYNERGISTIC_PATHWAY_WITH.value) + self.store.in_edges(pid, EdgeType.SYNERGISTIC_PATHWAY_WITH.value):
                line = f"- **{self.store.graph.nodes[s]['name'].split(' (')[0]}** ⇄ **{self.store.graph.nodes[t]['name'].split(' (')[0]}**: {d['properties'].get('rationale', '')}"
                if line not in synergy:
                    synergy.append(line)
            for _, c, d in self.store.out_edges(pid, EdgeType.CONTRAINDICATED_WITH.value):
                contra.append(f"- **{n.name.split(' (')[0]}** — {d['properties'].get('severity', 'Contraindicated')}: {self.store.graph.nodes[c]['name']}")
            if p.get("contraindication") and not self.store.out_edges(pid, EdgeType.CONTRAINDICATED_WITH.value):
                contra.append(f"- **{n.name.split(' (')[0]}** — {p['contraindication']}")
            for doc in _evidence_for(self.store, pid):
                citations[doc] = _citation(self.store, doc)
        if synergy:
            md.append("\n### Synergistic Pathway Map\n")
            md.extend(synergy)
        md.append("\n### Strict Contraindications\n")
        md.extend(contra or ["- No graph-linked contraindications for the focus products; consult the full prescribing information."])
        return {
            "agent_markdown": "\n".join(md),
            "agent_payload": {"focus_products": focus},
            "focus_node_ids": focus,
            "agent_subgraph": _subgraph_for(self.store, focus, hops=1),
            "citations": list(citations.values()),
            "execution_trace": [f"Domain Sub-Agent (pharma_clinical): traversed INDICATED_FOR / SYNERGISTIC_PATHWAY_WITH / "
                                f"HAS_BOXED_WARNING / CONTRAINDICATED_WITH edges for {focus}"],
        }

    def regulatory_auditor_agent(self, state: AgentState) -> Dict[str, Any]:
        retrieval = state["retrieval"]
        focus = _focus_nodes(self.store, retrieval, None, {NodeType.Product.value, NodeType.SoftwareModule.value}, limit=4)
        q = state["query"].lower()
        if "windchill" in q:
            for s, _, _ in self.store.in_edges("DOC_WINDCHILL_502735931", EdgeType.SUPPORTED_BY_EVIDENCE.value):
                if s not in focus:
                    focus.append(s)
        md: List[str] = ["## Regulatory Claim Provenance Audit", "",
                         "| Product | Claim Type | Claim | Evidence Source | Status |", "|---|---|---|---|---|"]
        citations: Dict[str, Dict[str, Any]] = {}
        lineage_lines: List[str] = []
        verified = 0
        total = 0
        for pid in focus:
            lin = self.store.claim_lineage(pid)
            name = lin["node"]["name"].split(" (")[0]
            docs = lin["evidence_documents"]
            doc_names = "; ".join(d["name"] for d in docs) or "—"
            for claim in lin["claims"]:
                total += 1
                status = "✅ Verified" if docs else "❌ Unverified"
                verified += 1 if docs else 0
                md.append(f"| **{name}** | {claim['type'].replace('_', ' ')} | {_cell(claim['text'])} | {_cell(doc_names, 90)} | {status} |")
            for d in docs:
                citations[d["id"]] = _citation(self.store, d["id"])
            lineage_lines += [f"- `{p}`" for p in lin["lineage_paths"]]
        md.append(f"\n**Provenance coverage:** {verified}/{total} claims traced to an EvidenceDocument "
                  f"({(verified / total * 100) if total else 0:.0f}%).")
        if lineage_lines:
            md.append("\n### Claim Lineage Paths\n")
            md.extend(lineage_lines)
        return {
            "agent_markdown": "\n".join(md),
            "agent_payload": {"audited_products": focus, "verified_claims": verified, "total_claims": total},
            "focus_node_ids": focus,
            "agent_subgraph": _subgraph_for(self.store, focus, hops=1),
            "citations": list(citations.values()),
            "execution_trace": [f"Domain Sub-Agent (regulatory_auditor): traced {total} claims for {focus} to "
                                f"EvidenceDocument/BoxedWarning nodes ({verified} verified)"],
        }

    def response_synthesizer(self, state: AgentState) -> Dict[str, Any]:
        retrieval = state["retrieval"]
        passages = retrieval["reranked_passages"]
        citations = {c["id"]: c for c in state.get("citations", [])}
        for p in passages:
            if p.get("label") == NodeType.EvidenceDocument.value and p["id"] not in citations:
                citations[p["id"]] = _citation(self.store, p["id"])
        cites = list(citations.values())
        for i, c in enumerate(cites, start=1):
            c["index"] = i

        md = [state["agent_markdown"], "\n### Top Evidence (Cross-Encoder Reranked)\n"]
        for p in passages[:6]:
            label = p.get("name") or p["text"]
            md.append(f"- `{p['cross_encoder_score']:.3f}` {_cell(label, 160)}")
        if cites:
            md.append("\n### Citations\n")
            md.extend(f"[{c['index']}] {c['title']}" + (f" — {c['source_url']}" if c.get("source_url") else "") for c in cites)
        draft = "\n".join(md)
        answer = _llm_polish(state["query"], draft) or draft

        sub = _merge_subgraphs(state.get("agent_subgraph", {}), retrieval["subgraph"])
        focus = set(state.get("focus_node_ids", [])) | set(retrieval["seeds"])
        sub["nodes"] = [n for n in sub["nodes"] if n["label"] not in HUB_TYPES or n["id"] in focus][:120]
        keep = {n["id"] for n in sub["nodes"]}
        for n in sub["nodes"]:
            n["is_focus"] = n["id"] in focus
            n.setdefault("color", NODE_COLORS.get(n["label"], "#CBD5E1"))
        sub["links"] = [l for l in sub["links"] if l["source"] in keep and l["target"] in keep]
        mode = get_settings().llm_mode
        return {
            "answer_markdown": answer,
            "subgraph": sub,
            "reranked_passages": passages,
            "citations": cites,
            "execution_trace": [f"Response Synthesizer: {len(cites)} citations, subgraph {len(sub['nodes'])} nodes / "
                                f"{len(sub['links'])} edges, generation mode={mode}"],
        }

    # ------------------------------------------------------------------ graph
    def _build(self):
        g = StateGraph(AgentState)
        g.add_node("supervisor_router", self.supervisor_router)
        g.add_node(MEDTECH, self.medtech_bundler_agent)
        g.add_node(PHARMA, self.pharma_clinical_agent)
        g.add_node(REGULATORY, self.regulatory_auditor_agent)
        g.add_node("response_synthesizer", self.response_synthesizer)
        g.set_entry_point("supervisor_router")
        g.add_conditional_edges("supervisor_router", lambda s: s["routed_agent"], {MEDTECH: MEDTECH, PHARMA: PHARMA, REGULATORY: REGULATORY})
        for a in (MEDTECH, PHARMA, REGULATORY):
            g.add_edge(a, "response_synthesizer")
        g.add_edge("response_synthesizer", END)
        return g.compile()

    def run(self, request: AgentQueryRequest) -> AgentQueryResponse:
        t0 = time.perf_counter()
        final = self.graph.invoke({"query": request.query, "max_hops": request.max_hops, "top_k": request.top_k, "execution_trace": []})
        return AgentQueryResponse(
            query=request.query,
            routed_agent=AGENT_LABELS[final["routed_agent"]],
            execution_trace=final["execution_trace"],
            answer_markdown=final["answer_markdown"],
            reranked_passages=final["reranked_passages"],
            subgraph=final["subgraph"],
            citations=final["citations"],
            latency_ms=round((time.perf_counter() - t0) * 1000, 2),
        )


def _llm_polish(query: str, grounded_draft: str) -> Optional[str]:
    """Optionally rewrite the grounded draft with a hosted LLM; returns None in local deterministic mode or on failure."""
    s = get_settings()
    instruction = ("You are a J&J enterprise analyst. Rewrite the grounded draft into a concise, well-structured Markdown answer to the "
                   "question. Use ONLY facts in the draft, keep all tables, numbers, warnings and the Citations section verbatim. "
                   "Never mention Kenvue consumer brands.")
    prompt = f"Question: {query}\n\nGrounded draft:\n{grounded_draft}"
    try:
        if s.openai_api_key:
            r = httpx.post("https://api.openai.com/v1/chat/completions", timeout=45,
                           headers={"Authorization": f"Bearer {s.openai_api_key}"},
                           json={"model": s.openai_model, "temperature": 0.1,
                                 "messages": [{"role": "system", "content": instruction}, {"role": "user", "content": prompt}]})
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        if s.gemini_api_key:
            r = httpx.post(f"https://generativelanguage.googleapis.com/v1beta/models/{s.gemini_model}:generateContent",
                           params={"key": s.gemini_api_key}, timeout=45,
                           json={"contents": [{"parts": [{"text": instruction + "\n\n" + prompt}]}], "generationConfig": {"temperature": 0.1}})
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as exc:
        logger.warning("LLM polish failed (%s); returning deterministic grounded answer", exc)
    return None


_runner: Optional[SupervisorRunner] = None


def get_supervisor(store: "GraphStore") -> SupervisorRunner:
    global _runner
    if _runner is None or _runner.store is not store:
        _runner = SupervisorRunner(store)
    return _runner
