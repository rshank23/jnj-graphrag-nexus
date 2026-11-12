import type {
  AgentQueryResponse,
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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init);
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
  return (await res.json()) as T;
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
