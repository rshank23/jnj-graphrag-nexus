import { useCallback, useState } from "react";
import { Activity, Bot, ClipboardCheck, KeyRound, Network, ShoppingCart, UserCircle2 } from "lucide-react";
import MetricsRibbon from "./components/MetricsRibbon";
import GraphExplorer from "./components/GraphExplorer";
import ProceduralBundler from "./components/ProceduralBundler";
import AgentCopilot from "./components/AgentCopilot";
import IngestionModal from "./components/IngestionModal";
import MLRReviewPanel from "./components/MLRReview";
import OpsDashboard from "./components/OpsDashboard";
import { session } from "./api/client";
import type { Role } from "./types/graph";

const ROLES: Role[] = ["medical", "mlr", "commercial", "admin"];

const TABS = [
  { id: "graph", label: "Knowledge Graph Explorer", icon: Network },
  { id: "bundler", label: "Procedural Cross-Sell Bundler", icon: ShoppingCart },
  { id: "copilot", label: "Multi-Agent Co-Pilot", icon: Bot },
  { id: "mlr", label: "MLR Pre-Review", icon: ClipboardCheck },
  { id: "ops", label: "Data Sources & Ops", icon: Activity },
] as const;

type TabId = (typeof TABS)[number]["id"];

export default function App() {
  const [tab, setTab] = useState<TabId>("graph");
  const [refreshKey, setRefreshKey] = useState(0);
  const [ingestOpen, setIngestOpen] = useState(false);
  const [role, setRole] = useState<Role>(session.role());
  const [apiKey, setApiKey] = useState(session.apiKey());
  const refresh = useCallback(() => setRefreshKey((k) => k + 1), []);
  const changeRole = (r: Role) => {
    session.setRole(r);
    setRole(r);
  };

  return (
    <div className="mx-auto flex min-h-full max-w-[1800px] flex-col gap-4 px-5 py-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-jnj font-black text-white shadow-lg shadow-jnj/30">J&amp;J</div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-white">
              GraphRAG <span className="text-jnj-light">Nexus</span>
            </h1>
            <p className="text-xs text-slate-400">Knowledge-graph intelligence for J&amp;J Innovative Medicine &amp; MedTech</p>
          </div>
        </div>
        <nav className="flex gap-1 rounded-xl border border-slate-800 bg-slate-900/70 p-1">
          {TABS.map((t) => {
            const Icon = t.icon;
            return (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition ${
                  tab === t.id ? "bg-jnj text-white shadow" : "text-slate-400 hover:bg-slate-800 hover:text-white"
                }`}
              >
                <Icon size={15} />
                {t.label}
              </button>
            );
          })}
        </nav>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-900/70 px-2 py-1.5 text-xs text-slate-400" title="Role sent as X-Nexus-Role (ignored when an API key is set)">
            <UserCircle2 size={14} />
            <select className="bg-transparent text-slate-200 outline-none" value={role} onChange={(e) => changeRole(e.target.value as Role)}>
              {ROLES.map((r) => (
                <option key={r} value={r} className="bg-slate-900">
                  {r}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-900/70 px-2 py-1.5 text-xs text-slate-400" title="Optional API key (X-Nexus-API-Key) when REQUIRE_API_KEY=true">
            <KeyRound size={14} />
            <input
              type="password"
              className="w-28 bg-transparent text-slate-200 outline-none placeholder-slate-600"
              placeholder="API key"
              value={apiKey}
              onChange={(e) => {
                setApiKey(e.target.value);
                session.setApiKey(e.target.value.trim());
              }}
            />
          </label>
        </div>
      </header>

      <MetricsRibbon refreshKey={refreshKey} onSync={() => setIngestOpen(true)} />

      <main className="flex-1">
        {tab === "graph" && <GraphExplorer refreshKey={refreshKey} />}
        {tab === "bundler" && <ProceduralBundler refreshKey={refreshKey} />}
        {tab === "copilot" && <AgentCopilot key={role} />}
        {tab === "mlr" && <MLRReviewPanel key={role} />}
        {tab === "ops" && <OpsDashboard key={role} onGraphChanged={refresh} />}
      </main>

      <footer className="pb-1 text-center text-[11px] text-slate-600">
        Hybrid BM25 + vector + 2-hop graph retrieval · LangGraph supervisor · MLR pre-review · openFDA / ClinicalTrials.gov / PubMed evidence · NetworkX / Neo4j dual store · Kenvue consumer brands excluded post-spinoff
      </footer>

      <IngestionModal open={ingestOpen} onClose={() => setIngestOpen(false)} onIngested={refresh} />
    </div>
  );
}
