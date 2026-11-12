import { useEffect, useState } from "react";
import { Boxes, DatabaseZap, GitBranch, Layers, RefreshCw, ShieldOff, TrendingUp } from "lucide-react";
import { api } from "../api/client";
import type { BundleResponse, HealthPayload } from "../types/graph";

interface Props {
  refreshKey: number;
  onSync: () => void;
}

function Metric({ icon, label, value, sub, accent }: { icon: React.ReactNode; label: string; value: string; sub?: string; accent?: string }) {
  return (
    <div className="panel flex items-center gap-3 px-4 py-3">
      <div className={`rounded-lg p-2 ${accent ?? "bg-clinical/10 text-clinical"}`}>{icon}</div>
      <div className="min-w-0">
        <div className="label-xs">{label}</div>
        <div className="text-xl font-bold leading-tight text-white">{value}</div>
        {sub && <div className="truncate text-[11px] text-slate-500">{sub}</div>}
      </div>
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

  const fmt = (n?: number) => (n === undefined ? "—" : n.toLocaleString("en-US"));

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="pill border-jnj/60 bg-jnj/10 text-white">
            <ShieldOff size={12} className="text-jnj-light" />
            Portfolio: J&amp;J Innovative Medicine + J&amp;J MedTech | Kenvue Excluded
          </span>
          {health && (
            <>
              <span className="pill border-slate-700 text-slate-400">
                <DatabaseZap size={12} /> Store: <span className="text-clinical">{health.active_store}</span>
              </span>
              <span className="pill border-slate-700 text-slate-400">
                LLM: <span className="text-clinical">{health.llm_mode}</span>
              </span>
            </>
          )}
          {error && <span className="pill border-red-800 bg-red-950/50 text-red-300">Backend unreachable: {error}</span>}
        </div>
        <button className="btn-primary" onClick={onSync}>
          <RefreshCw size={15} /> Sync Live J&amp;J / FDA DailyMed Data
        </button>
      </div>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Metric icon={<Boxes size={20} />} label="Total SKUs" value={fmt(health?.sku_count)} sub={health ? `${fmt(health.node_count)} total graph nodes` : undefined} />
        <Metric
          icon={<GitBranch size={20} />}
          label="Graph Edges"
          value={fmt(health?.edge_count)}
          sub="typed clinical & commercial relations"
          accent="bg-violet-500/10 text-violet-300"
        />
        <Metric
          icon={<Layers size={20} />}
          label="Active Franchises"
          value={fmt(health?.franchise_count)}
          sub={health ? Object.entries(health.division_breakdown).map(([k, v]) => `${k.replace("J&J ", "")}: ${v}`).join(" · ") : undefined}
          accent="bg-orange-500/10 text-orange-300"
        />
        <Metric
          icon={<TrendingUp size={20} />}
          label="Cross-Sell Uplift"
          value={bundle ? `${bundle.attachment_uplift_pct.toFixed(1)}%` : "—"}
          sub={bundle ? `AFib ablation @ ${bundle.annual_volume}/yr · $${fmt(Math.round(bundle.annual_consumable_cross_sell_usd))} pull-through` : undefined}
          accent="bg-emerald-500/10 text-emerald-300"
        />
      </div>
    </div>
  );
}
