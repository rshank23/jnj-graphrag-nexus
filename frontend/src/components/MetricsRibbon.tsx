import { useEffect, useState } from "react";
import { Boxes, DatabaseZap, GitBranch, Layers, RefreshCw, ShieldOff, TrendingUp } from "lucide-react";
import { api } from "../api/client";
import type { BundleResponse, HealthPayload } from "../types/graph";

interface Props {
  refreshKey: number;
  onSync: () => void;
}

const TONES = {
  cyan: { chip: "from-clinical/15 to-clinical/5 text-clinical ring-clinical/20", glow: "bg-clinical/15" },
  violet: { chip: "from-violet-600/15 to-violet-600/5 text-violet-300 ring-violet-600/20", glow: "bg-violet-500/15" },
  gold: { chip: "from-gold/15 to-gold/5 text-gold ring-gold/25", glow: "bg-gold/15" },
  emerald: { chip: "from-emerald-600/15 to-emerald-600/5 text-emerald-300 ring-emerald-600/20", glow: "bg-emerald-500/15" },
} as const;

function Metric({ icon, label, value, sub, tone, loading }: { icon: React.ReactNode; label: string; value: string; sub?: string; tone: keyof typeof TONES; loading?: boolean }) {
  const t = TONES[tone];
  return (
    <div className="panel panel-hover group relative overflow-hidden p-4 sm:p-5">
      <div className={`pointer-events-none absolute -right-10 -top-10 h-28 w-28 rounded-full opacity-60 blur-3xl transition-opacity duration-500 group-hover:opacity-100 ${t.glow}`} />
      <div className="relative flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="label-xs">{label}</div>
          {loading ? (
            <div className="mt-2 h-8 w-24 animate-shimmer rounded-lg bg-[linear-gradient(90deg,rgba(11,18,32,0.04),rgba(11,18,32,0.09),rgba(11,18,32,0.04))] bg-[length:200%_100%]" />
          ) : (
            <div className="mt-1.5 font-display text-[34px] leading-none tracking-tight text-white tabular-nums sm:text-[38px]">{value}</div>
          )}
        </div>
        <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ring-1 ring-inset ${t.chip}`}>{icon}</div>
      </div>
      {sub && <div className="relative mt-3 truncate text-[11.5px] text-slate-500">{sub}</div>}
    </div>
  );
}

export default function MetricsRibbon({ refreshKey, onSync }: Props) {
  const [health, setHealth] = useState<HealthPayload | null>(null);
  const [bundle, setBundle] = useState<BundleResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      api.health(),
      api.bundle({ procedure_id: "PROC_AFIB_ABLATION", annual_procedure_volume: 500, include_post_op_consumables: true }),
    ])
      .then(([h, b]) => {
        if (cancelled) return;
        setHealth(h);
        setBundle(b);
        setError(null);
      })
      .catch((e: Error) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  const fmt = (n?: number) => (n === undefined ? "\u2014" : n.toLocaleString("en-US"));
  const loading = !health && !error;

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="pill border-jnj/30 bg-gradient-to-r from-jnj/10 to-transparent text-slate-100">
            <ShieldOff size={12} className="text-jnj-light" />
            J&amp;J Innovative Medicine + MedTech
            <span className="mx-1 h-3 w-px bg-white/15" />
            <span className="text-slate-400">Kenvue excluded</span>
          </span>
          {health && (
            <span className="pill border-white/[0.08] bg-white/[0.02] text-slate-400">
              <DatabaseZap size={12} className="text-clinical" />
              <span className="font-mono text-[11px] text-slate-300">{health.active_store}</span>
              <span className="text-slate-600">/</span>
              <span className="font-mono text-[11px] text-slate-300">{health.llm_mode}</span>
            </span>
          )}
          {error && <span className="pill border-red-500/30 bg-red-500/10 text-red-300">Backend unreachable: {error}</span>}
        </div>
        <button className="btn-primary" onClick={onSync}>
          <RefreshCw size={15} /> Sync live J&amp;J / FDA data
        </button>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric tone="cyan" loading={loading} icon={<Boxes size={18} />} label="Total SKUs" value={fmt(health?.sku_count)} sub={health ? `${fmt(health.node_count)} total graph nodes` : undefined} />
        <Metric tone="violet" loading={loading} icon={<GitBranch size={18} />} label="Graph Edges" value={fmt(health?.edge_count)} sub="Typed clinical & commercial relations" />
        <Metric
          tone="gold"
          loading={loading}
          icon={<Layers size={18} />}
          label="Active Franchises"
          value={fmt(health?.franchise_count)}
          sub={health ? Object.entries(health.division_breakdown).map(([k, v]) => `${k.replace("J&J ", "")}: ${v}`).join(" \u00b7 ") : undefined}
        />
        <Metric
          tone="emerald"
          loading={loading}
          icon={<TrendingUp size={18} />}
          label="Cross-Sell Uplift"
          value={bundle ? `${bundle.attachment_uplift_pct.toFixed(1)}%` : "\u2014"}
          sub={bundle ? `AFib ablation @ ${bundle.annual_volume}/yr \u00b7 $${fmt(Math.round(bundle.annual_consumable_cross_sell_usd))} pull-through` : undefined}
        />
      </div>
    </section>
  );
}
