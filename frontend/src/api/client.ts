import type {
  AgentQueryResponse,
  EvalSummary,
  ExpandJob,
  MLRReview,
  MLRReviewListItem,
  Role,
  SourceStatus,
  UsageSummary,
  BundleRequest,
  BundleResponse,
  EgoPayload,
  GraphNodeData,
  GraphPayload,
  HealthPayload,
  IngestMode,
  IngestResponse,
} from "../types/graph";

const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

const ROLE_KEY = "nexus.role";
const API_KEY = "nexus.apiKey";

export const session = {
  role: (): Role => (localStorage.getItem(ROLE_KEY) as Role | null) ?? "medical",
  setRole: (r: Role) => localStorage.setItem(ROLE_KEY, r),
  apiKey: (): string => localStorage.getItem(API_KEY) ?? "",
  setApiKey: (k: string) => (k ? localStorage.setItem(API_KEY, k) : localStorage.removeItem(API_KEY)),
};

function authHeaders(): Record<string, string> {
  const h: Record<string, string> = { "X-Nexus-Role": session.role() };
  const key = session.apiKey();
  if (key) h["X-Nexus-API-Key"] = key;
  return h;
}

async function raw(path: string, init?: RequestInit): Promise<Response> {
  const res = await fetch(`${BASE}${path}`, { ...init, headers: { ...authHeaders(), ...(init?.headers ?? {}) } });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail || `HTTP ${res.status}`);
  }
  return res;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  return (await (await raw(path, init)).json()) as T;
}

async function download(path: string, init: RequestInit | undefined, fallbackName: string): Promise<void> {
  const res = await raw(path, init);
  const blob = await res.blob();
  const match = /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") ?? "");
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = match?.[1] ?? fallbackName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  health: () => request<HealthPayload>("/api/health"),

  graph: (params: { division?: string; nodeTypes?: string[]; search?: string }) => {
    const q = new URLSearchParams();
    if (params.division && params.division !== "All") q.set("division", params.division);
    if (params.nodeTypes && params.nodeTypes.length) q.set("node_type", params.nodeTypes.join(","));
    if (params.search) q.set("search", params.search);
    return request<GraphPayload>(`/api/graph?${q.toString()}`);
  },

  ego: (nodeId: string, hops = 2) => request<EgoPayload>(`/api/graph/ego/${encodeURIComponent(nodeId)}?hops=${hops}`),

  procedures: () => request<GraphNodeData[]>("/api/procedures"),

  bundle: (body: BundleRequest) => request<BundleResponse>("/api/bundle/recommend", json(body)),

  bundleDocx: (body: BundleRequest) => download("/api/bundle/export.docx", json(body), "bundle.docx"),

  me: () => request<{ name: string; role: Role; authenticated: boolean; tier?: string }>("/api/me"),

  feedback: (queryId: number, rating: -1 | 1, comment?: string) =>
    request<{ feedback_id: number }>("/api/feedback", json({ query_id: queryId, rating, comment })),

  mlrReview: (text: string, title?: string, useLlm = true) => request<MLRReview>("/api/mlr/review", json({ text, title, use_llm: useLlm })),
  mlrReviews: () => request<MLRReviewListItem[]>("/api/mlr/reviews"),
  mlrGet: (id: string) => request<MLRReview>(`/api/mlr/${encodeURIComponent(id)}`),
  mlrDecide: (id: string, findingId: string, decision: "accepted" | "rejected" | "revision", rationale?: string) =>
    request<Record<string, unknown>>(`/api/mlr/${encodeURIComponent(id)}/decisions`, json({ finding_id: findingId, decision, rationale })),
  mlrApproveClaim: (id: string, claimId: string) =>
    request<Record<string, unknown>>(`/api/mlr/${encodeURIComponent(id)}/claims/${encodeURIComponent(claimId)}/approve`, { method: "POST" }),
  mlrExport: (id: string) => download(`/api/mlr/${encodeURIComponent(id)}/export.docx`, undefined, `mlr_review_${id}.docx`),
  mlrLibrary: () => request<Record<string, unknown>[]>("/api/mlr/library"),

  sources: () => request<{ sources: SourceStatus[]; sync_modes: string[] }>("/api/sources/status"),
  sourceSync: (source: string, name: string) =>
    request<{ status: string; messages: string[]; added_nodes: unknown[]; added_edges: unknown[] }>(
      `/api/sources/sync/${encodeURIComponent(source)}`,
      json({ name }),
    ),
  sourcesRefresh: () => request<{ refreshed: number; results: { source: string; status: string; messages: string[] }[] }>("/api/sources/refresh", { method: "POST" }),
  expand: (name: string, division: string) => request<ExpandJob>("/api/expand", json({ name, division, background: true })),
  expandStatus: (jobId: string) => request<ExpandJob>(`/api/expand/${encodeURIComponent(jobId)}`),

  usage: () => request<UsageSummary>("/api/metrics/usage"),
  auditVerify: () => request<{ valid: boolean; entries: number; broken_at?: number | null }>("/api/audit/verify"),
  runEval: () => request<EvalSummary>("/api/eval/run", { method: "POST" }),
  prompts: () => request<{ name: string; version: string; description?: string }[]>("/api/prompts"),

  agentQuery: (query: string, topK = 5, maxHops = 2) =>
    request<AgentQueryResponse>("/api/agent/query", json({ query, top_k: topK, max_hops: maxHops })),

  ingest: (
    mode: IngestMode,
    fields: { drug_name?: string; url?: string; product_name?: string; product_text?: string; division?: string; franchise?: string; max_pages?: number },
    file?: File | null,
  ) => {
    if (mode === "pdf") {
      const form = new FormData();
      form.set("mode", "pdf");
      Object.entries(fields).forEach(([k, v]) => {
        if (v !== undefined && v !== "") form.set(k, String(v));
      });
      if (file) form.set("file", file);
      return request<IngestResponse>("/api/ingest/sync", { method: "POST", body: form });
    }
    return request<IngestResponse>("/api/ingest/sync", json({ mode, ...fields }));
  },
};
