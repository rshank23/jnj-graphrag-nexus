import { useEffect, useMemo, useState } from "react";
import { Activity, Cpu, DollarSign, Loader2, Package, Percent, ShieldPlus, Stethoscope, TrendingUp } from "lucide-react";
import { api } from "../api/client";
import type { BundleItem, BundleResponse, GraphNodeData } from "../types/graph";

const usd = (n: number) => `$${Math.round(n).toLocaleString("en-US")}`;

function TierCard({
  tier,
  title,
  icon,
  items,
  accent,
  volume,
  empty,
  recurring,
}: {
  tier: number;
  title: string;
  icon: React.ReactNode;
  items: BundleItem[];
  accent: string;
  volume: number;
  empty?: string;
  recurring?: boolean;
}) {
  const subtotal = items.reduce((s, i) => s + i.unit_price_usd, 0);
  return (
    <div className="panel flex flex-col p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className={`rounded-lg p-1.5 ${accent}`}>{icon}</div>
          <div>
            <div className="label-xs">Tier {tier}</div>
            <div className="text-sm font-semibold text-white">{title}</div>
          </div>
        </div>
        <div className="text-right">
          <div className="font-mono text-sm text-white">{usd(subtotal)}</div>
          <div className="text-[10px] text-slate-500">{recurring ? `per procedure · ${usd(subtotal * volume)}/yr` : "one-time"}</div>
        </div>
      </div>
      <div className="flex-1 space-y-2">
        {items.length === 0 && <div className="rounded-lg border border-dashed border-slate-700 p-3 text-xs text-slate-500">{empty ?? "No items mapped."}</div>}
        {items.map((i) => (
          <div key={i.id} className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
            <div className="flex items-start justify-between gap-2">
              <div className="text-sm font-medium text-slate-100">{i.name}</div>
              <div className="shrink-0 font-mono text-xs text-clinical">{usd(i.unit_price_usd)}</div>
            </div>
            <div className="mt-1 flex flex-wrap gap-1">
              <span className="pill border-slate-700 !px-1.5 !py-0 text-[10px] text-slate-400">{i.role_in_procedure}</span>
              {i.is_capital_equipment && <span className="pill border-amber-700 !px-1.5 !py-0 text-[10px] text-amber-300">capital</span>}
              {i.evidence_doc_id && <span className="pill border-emerald-800 !px-1.5 !py-0 text-[10px] text-emerald-300">{i.evidence_doc_id}</span>}
            </div>
            {i.clinical_claim && <p className="mt-1.5 text-xs italic leading-snug text-slate-400">“{i.clinical_claim}”</p>}
          </div>
        ))}
      </div>
    </div>
  );
}

function FinCard({ label, value, sub, icon, highlight }: { label: string; value: string; sub: string; icon: React.ReactNode; highlight?: boolean }) {
  return (
    <div className={`panel p-4 ${highlight ? "border-emerald-700/70 bg-emerald-950/30" : ""}`}>
      <div className="label-xs flex items-center gap-1.5">
        {icon}
        {label}
      </div>
      <div className={`mt-1 text-2xl font-bold ${highlight ? "text-emerald-300" : "text-white"}`}>{value}</div>
      <div className="mt-0.5 text-[11px] text-slate-500">{sub}</div>
    </div>
  );
}

export default function ProceduralBundler({ refreshKey }: { refreshKey: number }) {
  const [procedures, setProcedures] = useState<GraphNodeData[]>([]);
  const [procedureId, setProcedureId] = useState("PROC_AFIB_ABLATION");
  const [volume, setVolume] = useState(500);
  const [postOp, setPostOp] = useState(true);
  const [bundle, setBundle] = useState<BundleResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .procedures()
      .then((p) => {
        setProcedures(p);
        if (p.length && !p.some((x) => x.id === procedureId)) setProcedureId(p[0].id);
      })
      .catch((e: Error) => setError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshKey]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const t = setTimeout(() => {
      api
        .bundle({ procedure_id: procedureId, annual_procedure_volume: volume, include_post_op_consumables: postOp })
        .then((b) => {
          if (!cancelled) {
            setBundle(b);
            setError(null);
          }
        })
        .catch((e: Error) => !cancelled && setError(e.message))
        .finally(() => !cancelled && setLoading(false));
    }, 120);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [procedureId, volume, postOp, refreshKey]);

  const selected = useMemo(() => procedures.find((p) => p.id === procedureId), [procedures, procedureId]);

  return (
    <div className="space-y-4">
      <div className="panel grid gap-4 p-4 lg:grid-cols-[1.3fr_1.5fr_auto]">
        <div>
          <label className="label-xs mb-1.5 flex items-center gap-1.5">
            <Stethoscope size={12} /> Target Procedure
          </label>
          <select className="input" value={procedureId} onChange={(e) => setProcedureId(e.target.value)}>
            {procedures.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
          {selected && (
            <div className="mt-1.5 text-[11px] text-slate-500">
              {selected.franchise} · {String(selected.properties.anatomy ?? selected.properties.specialty ?? selected.division ?? "")}
            </div>
          )}
        </div>
        <div>
          <label className="label-xs mb-1.5 flex items-center justify-between">
            <span className="flex items-center gap-1.5">
              <Activity size={12} /> Annual Procedure Volume
            </span>
            <span className="font-mono text-base text-clinical">{volume.toLocaleString()}</span>
          </label>
          <input
            type="range"
            min={50}
            max={2000}
            step={10}
            value={volume}
            onChange={(e) => setVolume(Number(e.target.value))}
            className="mt-2 w-full accent-cyan-400"
          />
          <div className="flex justify-between text-[10px] text-slate-500">
            <span>50</span>
            <span>1,000</span>
            <span>2,000</span>
          </div>
        </div>
        <label className="flex cursor-pointer items-center gap-3 self-center rounded-lg border border-slate-700 px-3 py-2">
          <span className="relative">
            <input type="checkbox" className="peer sr-only" checked={postOp} onChange={(e) => setPostOp(e.target.checked)} />
            <span className="block h-5 w-9 rounded-full bg-slate-700 transition peer-checked:bg-emerald-500" />
            <span className="absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-white transition peer-checked:translate-x-4" />
          </span>
          <span className="text-sm text-slate-300">
            Include Ethicon
            <br />
            post-op consumables
          </span>
        </label>
      </div>

      {error && <div className="rounded-lg border border-red-900 bg-red-950/40 px-4 py-2 text-sm text-red-300">{error}</div>}

      {bundle && (
        <>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <FinCard
              icon={<DollarSign size={12} />}
              label="Baseline Capital Revenue"
              value={usd(bundle.baseline_capital_revenue_usd)}
              sub="Tier 1 capital + Tier 2 software"
            />
            <FinCard
              icon={<Package size={12} />}
              label="Per-Procedure Consumables"
              value={usd(bundle.per_procedure_consumable_revenue_usd)}
              sub="Tier 3 + Tier 4 per case"
            />
            <FinCard
              icon={<TrendingUp size={12} />}
              label="Annual Cross-Sell Pull-Through"
              value={usd(bundle.annual_consumable_cross_sell_usd)}
              sub={`${usd(bundle.per_procedure_consumable_revenue_usd)} × ${bundle.annual_volume.toLocaleString()} procedures`}
            />
            <FinCard
              icon={<Percent size={12} />}
              label="Total Year-1 Deal Value"
              value={usd(bundle.total_first_year_deal_value_usd)}
              sub={`Attachment uplift +${bundle.attachment_uplift_pct.toFixed(2)}% over capital`}
              highlight
            />
          </div>

          <div className={`grid gap-3 md:grid-cols-2 xl:grid-cols-4 ${loading ? "opacity-70" : ""}`}>
            <TierCard
              tier={1}
              title="Capital Platform"
              icon={<Cpu size={16} />}
              accent="bg-cyan-500/10 text-cyan-300"
              items={bundle.capital_platforms}
              volume={bundle.annual_volume}
            />
            <TierCard
              tier={2}
              title="Software Modules"
              icon={<Cpu size={16} />}
              accent="bg-violet-500/10 text-violet-300"
              items={bundle.software_modules}
              volume={bundle.annual_volume}
              empty="No dedicated software module for this platform."
            />
            <TierCard
              tier={3}
              title="Procedural Catheters, Sheaths & Implants"
              icon={<Package size={16} />}
              accent="bg-emerald-500/10 text-emerald-300"
              items={bundle.procedural_catheters_and_sheaths}
              recurring
              volume={bundle.annual_volume}
            />
            <TierCard
              tier={4}
              title="Post-Op Ethicon Consumables"
              icon={<ShieldPlus size={16} />}
              accent="bg-orange-500/10 text-orange-300"
              items={bundle.post_op_ethicon_consumables}
              recurring
              volume={bundle.annual_volume}
              empty={postOp ? "No post-op consumables mapped." : "Post-op consumables excluded (toggle above)."}
            />
          </div>
          <div className="panel p-4 text-xs leading-relaxed text-slate-400">
            <span className="font-semibold text-slate-200">Financial model: </span>
            Baseline = Σ Tier 1 capital + Σ Tier 2 software (one-time) · Per-procedure = Σ Tier 3 + Σ Tier 4 · Annual pull-through = per-procedure × volume ·
            Year-1 deal value = baseline + annual pull-through · Uplift % = annual pull-through ÷ baseline × 100. All tiers are derived live by traversing{" "}
            <code className="text-cyan-300">PRIMARY_PLATFORM_FOR</code>, <code className="text-cyan-300">INTEGRATES_WITH</code>,{" "}
            <code className="text-cyan-300">COMPATIBLE_ACCESSORY</code> and <code className="text-cyan-300">POST_OP_*</code> edges.
          </div>
        </>
      )}
      {!bundle && loading && (
        <div className="flex items-center gap-2 text-sm text-slate-400">
          <Loader2 size={14} className="animate-spin" /> Computing bundle…
        </div>
      )}
    </div>
  );
}
