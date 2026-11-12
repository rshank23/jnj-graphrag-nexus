export type NodeLabel =
  | "BusinessUnit"
  | "Franchise"
  | "Product"
  | "SoftwareModule"
  | "Procedure"
  | "Anatomy"
  | "ClinicalCondition"
  | "EvidenceDocument"
  | "BoxedWarning"
  | "HardwareCoupling";

export const ALL_NODE_LABELS: NodeLabel[] = [
  "Product",
  "SoftwareModule",
  "Procedure",
  "Anatomy",
  "ClinicalCondition",
  "EvidenceDocument",
  "BoxedWarning",
  "HardwareCoupling",
  "Franchise",
  "BusinessUnit",
];

export const DEFAULT_NODE_LABELS: NodeLabel[] = [
  "Product",
  "SoftwareModule",
  "Procedure",
  "Anatomy",
  "ClinicalCondition",
  "EvidenceDocument",
  "BoxedWarning",
  "HardwareCoupling",
];

export const DIVISIONS = ["All", "J&J MedTech", "J&J Innovative Medicine"] as const;
export type Division = (typeof DIVISIONS)[number];

export interface GraphNodeData {
  id: string;
  label: NodeLabel;
  name: string;
  division?: string | null;
  franchise?: string | null;
  properties: Record<string, unknown>;
  color?: string;
  degree?: number;
  hop?: number;
  is_seed?: boolean;
  is_focus?: boolean;
}

export interface GraphLinkData {
  source: string;
  target: string;
  relation: string;
  properties?: Record<string, unknown>;
}

export interface GraphPayload {
  nodes: GraphNodeData[];
  links: GraphLinkData[];
}

export interface ClaimLineage {
  node: GraphNodeData;
  claims: { type: string; text: string }[];
  evidence_documents: GraphNodeData[];
  boxed_warnings: GraphNodeData[];
  contraindications: (GraphNodeData & { severity?: string })[];
  lineage_paths: string[];
  provenance_status: string;
}

export interface EgoPayload extends GraphPayload {
  center: GraphNodeData;
  hops: number;
  paths: string[];
  one_hop: string[];
  two_hop: string[];
  claims: { type: string; text: string }[];
  lineage: ClaimLineage;
}

export interface HealthPayload {
  status: string;
  backend: string;
  active_store: string;
  llm_mode: string;
  node_count: number;
  edge_count: number;
  sku_count: number;
  franchise_count: number;
  division_breakdown: Record<string, number>;
  label_breakdown: Record<string, number>;
}

export interface BundleItem {
  id: string;
  name: string;
  category: string;
  role_in_procedure: string;
  unit_price_usd: number;
  is_capital_equipment: boolean;
  clinical_claim?: string | null;
  evidence_doc_id?: string | null;
}

export interface BundleRequest {
  procedure_id: string;
  annual_procedure_volume: number;
  include_post_op_consumables: boolean;
}

export interface BundleResponse {
  procedure_id: string;
  procedure_name: string;
  annual_volume: number;
  capital_platforms: BundleItem[];
  software_modules: BundleItem[];
  procedural_catheters_and_sheaths: BundleItem[];
  post_op_ethicon_consumables: BundleItem[];
  baseline_capital_revenue_usd: number;
  per_procedure_consumable_revenue_usd: number;
  annual_consumable_cross_sell_usd: number;
  total_first_year_deal_value_usd: number;
  attachment_uplift_pct: number;
}

export interface RerankedPassage {
  id: string;
  type: "passage" | "graph_path";
  label?: string;
  name?: string;
  text: string;
  hop: number;
  rrf_score: number;
  cross_encoder_score: number;
  node_ids: string[];
}

export interface Citation {
  id: string;
  title: string;
  doc_type?: string | null;
  source_url?: string | null;
  published?: string | null;
  windchill_id?: string | null;
}

export interface AgentQueryResponse {
  query: string;
  routed_agent: "medtech_bundler" | "pharma_clinical" | "regulatory_auditor";
  execution_trace: string[];
  answer_markdown: string;
  reranked_passages: RerankedPassage[];
  subgraph: GraphPayload;
  citations: Citation[];
  latency_ms: number;
}

export type IngestMode = "live" | "dailymed" | "url" | "text" | "pdf";

export interface IngestResponse {
  mode: string;
  status: string;
  messages: string[];
  rejected_kenvue_brands: string[];
  added_nodes: GraphNodeData[];
  added_edges: GraphLinkData[];
  node_count: number;
  edge_count: number;
}

export const NODE_COLORS: Record<NodeLabel, string> = {
  BusinessUnit: "#D51900",
  Franchise: "#F97316",
  Product: "#22D3EE",
  SoftwareModule: "#A78BFA",
  Procedure: "#34D399",
  Anatomy: "#F472B6",
  ClinicalCondition: "#FBBF24",
  EvidenceDocument: "#94A3B8",
  BoxedWarning: "#EF4444",
  HardwareCoupling: "#60A5FA",
};
