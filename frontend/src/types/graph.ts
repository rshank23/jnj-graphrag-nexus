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
  | "HardwareCoupling"
  | "ClinicalTrial"
  | "Publication"
  | "SafetySignal"
  | "LabelChange"
  | "Recall";

export const ALL_NODE_LABELS: NodeLabel[] = [
  "Product",
  "SoftwareModule",
  "Procedure",
  "Anatomy",
  "ClinicalCondition",
  "EvidenceDocument",
  "BoxedWarning",
  "HardwareCoupling",
  "ClinicalTrial",
  "Publication",
  "SafetySignal",
  "LabelChange",
  "Recall",
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
  "ClinicalTrial",
  "Publication",
  "SafetySignal",
  "LabelChange",
  "Recall",
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
  auth_required?: boolean;
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
  confidence: number;
  risk_level: "low" | "medium" | "high" | "blocked";
  guardrails: { type?: string; detail?: string; [k: string]: unknown }[];
  in_scope: boolean;
  query_id?: number | null;
  disclaimer?: string | null;
  llm?: { provider: string; model: string; prompt_version: string; cost_usd?: number } | null;
}

export type EvidenceMode =
  | "openfda_label"
  | "faers"
  | "drug_recalls"
  | "device_recalls"
  | "gudid"
  | "maude"
  | "clinicaltrials"
  | "pubmed"
  | "expand";

export type IngestMode = "live" | "dailymed" | "url" | "text" | "pdf" | EvidenceMode;

export type Role = "commercial" | "medical" | "mlr" | "admin";

export type Severity = "critical" | "warning" | "unverified" | "info";

export interface MLRFinding {
  id: string;
  claim_id?: string | null;
  check: string;
  severity: Severity;
  title: string;
  detail: string;
  evidence: Record<string, unknown>[];
  suggestion?: string | null;
  precedents: Record<string, string>[];
  anchor?: { start: number; end: number } | null;
  decision?: { decision: string; rationale?: string | null; reviewer?: string | null; ts: string } | null;
}

export interface MLRClaim {
  id: string;
  text: string;
  start: number;
  end: number;
  claim_types: string[];
  product_ids: string[];
  verdict: string;
  confidence: number;
  library_match?: Record<string, unknown> | null;
  finding_ids: string[];
}

export interface MLRReview {
  review_id: string;
  title: string;
  created: string;
  asset_text: string;
  claims: MLRClaim[];
  findings: MLRFinding[];
  summary: {
    severity_counts: Record<Severity, number>;
    risk_score: number;
    status: "not-ready" | "needs-review" | "ready-for-mlr";
    claims: number;
    verdicts: Record<string, number>;
    products: string[];
    library_matches: number;
  };
  latency_ms: number;
  disclaimer: string;
  decisions?: { finding_id: string; decision: string; rationale?: string | null; reviewer?: string | null; ts: string }[];
}

export interface SourceStatus {
  source: string;
  cadence: string;
  last_success: string | null;
  last_error: string | null;
  items: number;
  age_hours: number | null;
  due: boolean;
  status: string;
}

export interface MLRReviewListItem {
  review_id: string;
  created: string;
  title: string;
  actor?: string | null;
  summary: MLRReview["summary"];
  findings: number;
  decided: number;
}

export interface UsageSummary {
  queries: number;
  unique_users: number;
  avg_latency_ms: number;
  avg_confidence: number;
  llm_cost_usd: number;
  by_agent: { routed_agent: string; n: number }[];
  by_risk: { risk_level: string; n: number }[];
  feedback: { total: number; positive: number; satisfaction_pct: number | null };
  daily: { day: string; n: number }[];
  tool_calls: { tool: string; n: number; avg_ms: number; errors: number }[];
  llm_usage: { provider: string; model: string; calls: number; prompt_tokens: number; completion_tokens: number; cost_usd: number }[];
  mlr_reviews: number;
  mlr_decisions: { decision: string; n: number }[];
}

export interface ExpandJob {
  job_id: string;
  query: string;
  division: string;
  phase1: { product_id?: string | null; method: string; name?: string; created?: boolean; messages?: string[] };
  status: "running" | "complete" | "failed";
  current_step: string | null;
  steps: { step: string; status: string; messages: string[]; added_nodes: number; added_edges: number }[];
}

export interface EvalSummary {
  n: number;
  k: number;
  methods: Record<string, Record<string, number>>;
  routing_accuracy: number;
  citation_precision: number;
  groundedness?: number;
  answer_entity_hit?: number;
  failures: { id: string; query: string; expected: string[]; got_top: string[]; expected_agent: string; routed: string }[];
  dense_method: string;
  reranker: string;
  elapsed_s: number;
}

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
  Franchise: "#EA580C",
  Product: "#0A7C93",
  SoftwareModule: "#7C3AED",
  Procedure: "#059669",
  Anatomy: "#DB2777",
  ClinicalCondition: "#D97706",
  EvidenceDocument: "#64748B",
  BoxedWarning: "#DC2626",
  HardwareCoupling: "#2563EB",
  ClinicalTrial: "#0D9488",
  Publication: "#94A3B8",
  SafetySignal: "#E11D48",
  LabelChange: "#CA8A04",
  Recall: "#B91C1C",
};
