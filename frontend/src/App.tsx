import { useCallback, useEffect, useState } from "react";
import { Activity, Bot, ClipboardCheck, KeyRound, Network, ShieldCheck, ShoppingCart, Sparkles, UserCircle2 } from "lucide-react";
import MetricsRibbon from "./components/MetricsRibbon";
import GraphExplorer from "./components/GraphExplorer";
import ProceduralBundler from "./components/ProceduralBundler";
import AgentCopilot from "./components/AgentCopilot";
import IngestionModal from "./components/IngestionModal";
import MLRReviewPanel from "./components/MLRReview";
import OpsDashboard from "./components/OpsDashboard";
import { api, session } from "./api/client";
import type { HealthPayload, Role } from "./types/graph";

const ROLES: Role[] = ["medical", "mlr", "commercial", "admin"];

const TABS = [
  {
    id: "graph",
    label: "Knowledge Graph",
    blurb: "Explorer",
    icon: Network,
    eyebrow: "Portfolio intelligence",
    title: "Knowledge Graph Explorer",
    desc: "Navigate products, indications, procedures and evidence across Innovative Medicine and MedTech.",
  },
  {
    id: "bundler",
    label: "Cross-Sell Bundler",
    blurb: "Procedural",
    icon: ShoppingCart,
    eyebrow: "Commercial value",
    title: "Procedural Cross-Sell Bundler",
    desc: "Model procedure-level pull-through and consumable attachment across the MedTech portfolio.",
  },
  {
    id: "copilot",
    label: "Agent Co-Pilot",
    blurb: "Multi-agent",
    icon: Bot,
    eyebrow: "Grounded reasoning",
    title: "Multi-Agent Co-Pilot",
    desc: "Ask questions answered by a LangGraph supervisor with graph-grounded, cited evidence.",
  },
  {
    id: "mlr",
    label: "MLR Pre-Review",
    blurb: "Compliance",
    icon: ClipboardCheck,
    eyebrow: "Medical · Legal · Regulatory",
    title: "MLR Pre-Review",
    desc: "Screen promotional claims against labelled indications and fair-balance requirements before submission.",
  },
  {
    id: "ops",
    label: "Sources & Ops",
    blurb: "Data plane",
    icon: Activity,
    eyebrow: "Operations",
    title: "Data Sources & Ops",
    desc: "Live evidence connectors, audit trail integrity and retrieval quality evaluations.",
  },
] as const;

type TabId = (typeof TABS)[number]["id"];

function BrandMark() {
  return (
    <div className="flex items-center gap-3">
      <div className="relative flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-[#f0432a] via-jnj to-jnj-dark text-[13px] font-black tracking-tight text-snow shadow-brand ring-1 ring-inset ring-black/5">
        J&amp;J
      </div>
      <div className="leading-tight">
        <div className="text-[15px] font-semibold tracking-tight text-white">
          GraphRAG <span className="display text-[19px] italic text-gold-light">Nexus</span>
        </div>
        <div className="text-[11px] text-slate-500">Knowledge intelligence</div>
      </div>
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState<TabId>("graph");
  const [refreshKey, setRefreshKey] = useState(0);
  const [ingestOpen, setIngestOpen] = useState(false);
  const [role, setRole] = useState<Role>(session.role());
  const [apiKey, setApiKey] = useState(session.apiKey());
  const [health, setHealth] = useState<HealthPayload | null>(null);
  const [online, setOnline] = useState<boolean | null>(null);
  const refresh = useCallback(() => setRefreshKey((k) => k + 1), []);
  const changeRole = (r: Role) => {
    session.setRole(r);
    setRole(r);
  };
  const active = TABS.find((t) => t.id === tab)!;

  useEffect(() => {
    let cancelled = false;
    api
      .health()
      .then((h) => {
        if (cancelled) return;
        setHealth(h);
        setOnline(true);
      })
      .catch(() => !cancelled && setOnline(false));
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  const sessionControls = (
    <div className="space-y-2">
      <label className="flex items-center gap-2 rounded-xl border border-white/[0.07] bg-snow px-3 py-2 text-xs text-slate-400 shadow-sm transition focus-within:border-clinical/50" title="Role sent as X-Nexus-Role (ignored when an API key is set)">
        <UserCircle2 size={14} className="shrink-0 text-slate-500" />
        <span className="text-slate-500">Role</span>
        <select className="ml-auto cursor-pointer bg-transparent text-right font-medium capitalize text-slate-100 outline-none" value={role} onChange={(e) => changeRole(e.target.value as Role)}>
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
      </label>
      <label className="flex items-center gap-2 rounded-xl border border-white/[0.07] bg-snow px-3 py-2 text-xs text-slate-400 shadow-sm transition focus-within:border-clinical/50" title="Optional API key (X-Nexus-API-Key) when REQUIRE_API_KEY=true">
        <KeyRound size={14} className="shrink-0 text-slate-500" />
        <input
          type="password"
          className="w-full min-w-0 bg-transparent text-slate-100 outline-none placeholder:text-slate-600"
          placeholder="API key (optional)"
          value={apiKey}
          onChange={(e) => {
            setApiKey(e.target.value);
            session.setApiKey(e.target.value.trim());
          }}
        />
      </label>
    </div>
  );

  return (
    <div className="flex min-h-full">
      <aside className="sticky top-0 hidden h-screen w-[264px] shrink-0 flex-col border-r border-slate-800 bg-snow/70 px-4 py-5 backdrop-blur-xl lg:flex">
        <BrandMark />
        <div className="hairline my-5" />
        <div className="label-xs mb-2 px-3">Workspace</div>
        <nav className="space-y-1">
          {TABS.map((t) => {
            const Icon = t.icon;
            const isActive = tab === t.id;
            return (
              <button key={t.id} onClick={() => setTab(t.id)} className={`nav-item group ${isActive ? "nav-item-active" : ""}`}>
                {isActive && <span className="absolute -left-4 top-1/2 h-6 w-[3px] -translate-y-1/2 rounded-r-full bg-gradient-to-b from-jnj-light to-jnj" />}
                <span
                  className={`flex h-8 w-8 items-center justify-center rounded-lg border transition ${
                    isActive ? "border-jnj/40 bg-jnj/15 text-jnj-light" : "border-white/[0.06] bg-white/[0.02] text-slate-500 group-hover:text-slate-200"
                  }`}
                >
                  <Icon size={15} />
                </span>
                <span className="min-w-0">
                  <span className="block truncate">{t.label}</span>
                  <span className="block text-[10.5px] font-normal text-slate-500">{t.blurb}</span>
                </span>
              </button>
            );
          })}
        </nav>

        <div className="mt-auto space-y-3">
          <div className="label-xs px-1">Session</div>
          {sessionControls}
          <div className="rounded-xl border border-white/[0.06] bg-snow p-3 shadow-sm">
            <div className="flex items-center gap-2 text-xs">
              <span className={`h-2 w-2 rounded-full ${online === false ? "bg-red-400" : online ? "animate-pulseRing bg-emerald-400" : "bg-slate-500"}`} />
              <span className="font-medium text-slate-200">{online === false ? "Backend offline" : online ? "All systems operational" : "Connecting…"}</span>
            </div>
            {health && (
              <div className="mt-2 grid grid-cols-2 gap-1 font-mono text-[10.5px] text-slate-500">
                <span>store</span>
                <span className="text-right text-clinical">{health.active_store}</span>
                <span>llm</span>
                <span className="truncate text-right text-clinical">{health.llm_mode}</span>
              </div>
            )}
          </div>
          <div className="flex items-center gap-1.5 px-1 text-[10.5px] text-slate-600">
            <ShieldCheck size={12} /> Kenvue consumer brands excluded
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 border-b border-white/[0.06] bg-snow/80 px-4 py-3 backdrop-blur-xl lg:hidden">
          <div className="flex items-center justify-between gap-3">
            <BrandMark />
          </div>
          <nav className="mt-3 flex gap-1 overflow-x-auto pb-1">
            {TABS.map((t) => {
              const Icon = t.icon;
              return (
                <button
                  key={t.id}
                  onClick={() => setTab(t.id)}
                  className={`flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                    tab === t.id ? "bg-snow text-slate-50 shadow-sm ring-1 ring-inset ring-slate-800" : "text-slate-400 hover:text-white"
                  }`}
                >
                  <Icon size={13} />
                  {t.label}
                </button>
              );
            })}
          </nav>
          <div className="mt-2 grid grid-cols-2 gap-2 [&>div]:contents">{sessionControls}</div>
        </header>

        <div className="mx-auto flex w-full max-w-[1640px] flex-1 flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <div key={`hdr-${active.id}`} className="flex animate-fadeUp flex-wrap items-end justify-between gap-4">
            <div className="max-w-2xl">
              <div className="label-xs flex items-center gap-1.5 text-clinical/80">
                <Sparkles size={11} /> {active.eyebrow}
              </div>
              <h1 className="display mt-1.5 text-[34px] leading-[1.05] sm:text-[40px]">{active.title}</h1>
              <p className="mt-2 text-sm leading-relaxed text-slate-400">{active.desc}</p>
            </div>
          </div>

          <MetricsRibbon refreshKey={refreshKey} onSync={() => setIngestOpen(true)} />

          <main key={`main-${tab}`} className="flex-1 animate-fadeUp">
            {tab === "graph" && <GraphExplorer refreshKey={refreshKey} />}
            {tab === "bundler" && <ProceduralBundler refreshKey={refreshKey} />}
            {tab === "copilot" && <AgentCopilot key={role} />}
            {tab === "mlr" && <MLRReviewPanel key={role} />}
            {tab === "ops" && <OpsDashboard key={role} onGraphChanged={refresh} />}
          </main>

          <footer className="border-t border-white/[0.05] pt-4 text-center text-[11px] leading-relaxed text-slate-600">
            Hybrid BM25 + vector + 2-hop graph retrieval · LangGraph supervisor · MLR pre-review · openFDA / ClinicalTrials.gov / PubMed evidence · NetworkX / Neo4j dual store
          </footer>
        </div>
      </div>

      <IngestionModal open={ingestOpen} onClose={() => setIngestOpen(false)} onIngested={refresh} />
    </div>
  );
}
