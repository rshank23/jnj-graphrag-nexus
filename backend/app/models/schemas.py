"""Strict Pydantic v2 schemas for graph entities, BOM bundles, agents and ingestion."""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class NodeType(str, Enum):
    BusinessUnit = "BusinessUnit"
    Franchise = "Franchise"
    Product = "Product"
    SoftwareModule = "SoftwareModule"
    Procedure = "Procedure"
    Anatomy = "Anatomy"
    ClinicalCondition = "ClinicalCondition"
    EvidenceDocument = "EvidenceDocument"
    BoxedWarning = "BoxedWarning"
    HardwareCoupling = "HardwareCoupling"


class EdgeType(str, Enum):
    BELONGS_TO_UNIT = "BELONGS_TO_UNIT"
    IN_FRANCHISE = "IN_FRANCHISE"
    PRIMARY_PLATFORM_FOR = "PRIMARY_PLATFORM_FOR"
    INTEGRATES_WITH = "INTEGRATES_WITH"
    AUTO_SEGMENTS_3D_CT = "AUTO_SEGMENTS_3D_CT"
    COMPATIBLE_ACCESSORY = "COMPATIBLE_ACCESSORY"
    GUIDES_TRANSSEPTAL_PUNCTURE = "GUIDES_TRANSSEPTAL_PUNCTURE"
    POST_OP_INFECTION_CONTROL_FOR = "POST_OP_INFECTION_CONTROL_FOR"
    POST_OP_DRAINAGE_FOR = "POST_OP_DRAINAGE_FOR"
    INDICATED_FOR = "INDICATED_FOR"
    SYNERGISTIC_PATHWAY_WITH = "SYNERGISTIC_PATHWAY_WITH"
    CONTRAINDICATED_WITH = "CONTRAINDICATED_WITH"
    SUPPORTED_BY_EVIDENCE = "SUPPORTED_BY_EVIDENCE"
    HAS_BOXED_WARNING = "HAS_BOXED_WARNING"
    COMPATIBLE_COUPLING = "COMPATIBLE_COUPLING"


class GraphNode(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: str = Field(..., min_length=1)
    label: NodeType
    name: str = Field(..., min_length=1)
    division: Optional[str] = None
    franchise: Optional[str] = None
    properties: Dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    source: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)
    relation: EdgeType
    properties: Dict[str, Any] = Field(default_factory=dict)


class BundleRequest(BaseModel):
    procedure_id: str
    annual_procedure_volume: int = Field(default=500, ge=1, le=100_000)
    include_post_op_consumables: bool = True


class BundleItem(BaseModel):
    id: str
    name: str
    category: str
    role_in_procedure: str
    unit_price_usd: float
    is_capital_equipment: bool
    clinical_claim: Optional[str] = None
    evidence_doc_id: Optional[str] = None


class BundleResponse(BaseModel):
    procedure_id: str
    procedure_name: str
    annual_volume: int
    capital_platforms: List[BundleItem]
    software_modules: List[BundleItem]
    procedural_catheters_and_sheaths: List[BundleItem]
    post_op_ethicon_consumables: List[BundleItem]
    baseline_capital_revenue_usd: float
    per_procedure_consumable_revenue_usd: float
    annual_consumable_cross_sell_usd: float
    total_first_year_deal_value_usd: float
    attachment_uplift_pct: float


class AgentQueryRequest(BaseModel):
    query: str = Field(..., min_length=2)
    max_hops: int = Field(default=2, ge=1, le=3)
    top_k: int = Field(default=5, ge=1, le=20)


class AgentQueryResponse(BaseModel):
    query: str
    routed_agent: str
    execution_trace: List[str]
    answer_markdown: str
    reranked_passages: List[Dict[str, Any]]
    subgraph: Dict[str, Any]
    citations: List[Dict[str, Any]]
    latency_ms: float


class IngestSyncRequest(BaseModel):
    mode: str = Field(default="text", description="one of: live, dailymed, text, url")
    drug_name: Optional[str] = None
    url: Optional[str] = None
    product_name: Optional[str] = None
    product_text: Optional[str] = None
    division: Optional[str] = None
    franchise: Optional[str] = None
    max_pages: int = Field(default=2, ge=1, le=10)


class ScrapedProduct(BaseModel):
    name: str
    generic_name: Optional[str] = None
    division: str
    franchise: Optional[str] = None
    description: Optional[str] = None
    has_boxed_warning: bool = False
    prescribing_info_url: Optional[str] = None
    source_url: str
    compatibility: List[str] = Field(default_factory=list)


class IngestSyncResponse(BaseModel):
    mode: str
    status: str
    messages: List[str]
    rejected_kenvue_brands: List[str]
    added_nodes: List[GraphNode]
    added_edges: List[GraphEdge]
    node_count: int
    edge_count: int
