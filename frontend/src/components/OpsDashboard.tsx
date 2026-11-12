import { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity,
  BarChart3,
  CheckCircle2,
  Database,
  FlaskConical,
  Link2,
  Loader2,
  PlusCircle,
  RefreshCw,
  ScrollText,
  ShieldAlert,
  ThumbsUp,
} from "lucide-react";
import { api } from "../api/client";
import type { EvalSummary, ExpandJob, SourceStatus, UsageSummary } from "../types/graph";

const STATUS_STYLE: Record<string, string> = {
  fresh: "border-emerald-700 text-emerald-300",
  stale: "border-amber-700 text-amber-300",
  error: "border-red-700 text-red-300",
  never: "border-slate-700 text-slate-400",
  ok: "border-emerald-700 text-emerald-300",
};

function Stat({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950/50 px-3 py-2">
      <div className="label-xs">{label}</div>
      <div className="mt-0.5 text-lg font-bold text-white">{value}</div>
      {sub && <div className="text-[10px] text-slate-500">{sub}</div>}
    </div>
  );
}

function Bars({ rows }: { rows: { k: string; n: number }[] }) {
  const max = Math.max(1, ...rows.map((r) => r.n));
  if (!rows.length) return <div className="text-xs text-slate-500">No data yet.</div>;
  return (
    <div className="space-y-1">
      {rows.map((r) => (
        <div key={r.k} className="flex items-center gap-2 text-xs">
          <span className="w-36 truncate text-slate-400">{r.k}</span>
          <div className="h-2 flex-1 rounded bg-slate-800">
            <div className="h-2 rounded bg-clinical" style={{ width: `${(r.n / max) * 100}%` }} />
          </div>
          <span className="w-8 text-right font-mono text-slate-300">{r.n}</span>
        </div>
      ))}
    </div>
  );
}

function SourcesPanel({ onGraphChanged }: { onGraphChanged: () => void }) {
  const [sources, setSources] = useState<SourceStatus[]>([]);
  const [modes, setModes] = useState<string[]>([]);
  const [mode, setMode] = useState("openfda_label");
  const [name, setName] = useState("TREMFYA");
  const [busy, setBusy] = useState(false);
  const [log, setLog] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .sources()
      .then((r) => {
        setSources(r.sources);
        setModes(r.sync_modes);
      })
      .catch((e) => setError((e as Error).message));
  }, []);
  useEffect(load, [load]);

  const sync = async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await api.sourceSync(mode, name);
      setLog([`${mode} · ${name}: ${r.status} (+${r.added_nodes.length} nodes, +${r.added_edges.length} edges)`, ...r.messages]);
      load();
      onGraphChanged();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const refreshDue = async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await api.sourcesRefresh();
      setLog([`Refreshed ${r.refreshed} due source(s)`, ...r.results.flatMap((x) => [`${x.source}: ${x.status}`, ...x.messages.slice(0, 3)])]);
      load();
      onGraphChanged();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="panel p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="label-xs flex items-center gap-1.5">
          <Database size={12} /> Evidence sources · freshness
        </div>
        <button className="btn-ghost !py-1 text-xs" disabled={busy} onClick={refreshDue}>
          <RefreshCw size={12} className={busy ? "animate-spin" : ""} /> Refresh due
        </button>
      </div>
      <table className="w-full text-left text-xs">
        <thead className="text-slate-500">
          <tr>
            <th className="py-1">Source</th>
            <th className="py-1">Cadence</th>
            <th className="py-1">Last success</th>
            <th className="py-1 text-right">Items</th>
            <th className="py-1 text-right">Status</th>
          </tr>
        </thead>
        <tbody>
          {sources.map((s) => (
            <tr key={s.source} className="border-t border-slate-800/80" title={s.last_error ?? ""}>
              <td className="py-1.5 font-mono text-slate-300">{s.source}</td>
              <td className="py-1.5 text-slate-400">{s.cadence}</td>
              <td className="py-1.5 text-slate-400">
                {s.last_success ? `${new Date(s.last_success).toLocaleString()}${s.age_hours != null ? ` (${s.age_hours.toFixed(1)}h)` : ""}` : "—"}
              </td>
              <td className="py-1.5 text-right font-mono text-slate-300">{s.items}</td>
              <td className="py-1.5 text-right">
                <span className={`pill !py-0 text-[10px] ${STATUS_STYLE[s.status] ?? "border-slate-700 text-slate-400"}`}>
                  {s.status}
                  {s.due ? " · due" : ""}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-3 grid grid-cols-[180px_1fr_auto] gap-2">
        <select className="input !py-1.5 text-xs" value={mode} onChange={(e) => setMode(e.target.value)}>
          {modes.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
        <input className="input !py-1.5 text-xs" value={name} onChange={(e) => setName(e.target.value)} placeholder="Drug / device / product name" />
        <button className="btn-primary !py-1.5 text-xs" disabled={busy || !name.trim()} onClick={sync}>
          {busy ? <Loader2 size={12} className="animate-spin" /> : <Link2 size={12} />} Sync
        </button>
      </div>
      {error && <div className="mt-2 text-xs text-red-300">{error}</div>}
      {log.length > 0 && (
        <ul className="mt-2 max-h-40 overflow-y-auto rounded border border-slate-800 bg-slate-950/60 p-2 font-mono text-[11px] text-slate-400">
          {log.map((l, i) => (
            <li key={i}>{l}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ExpandPanel({ onGraphChanged }: { onGraphChanged: () => void }) {
  const [name, setName] = useState("RYBREVANT");
  const [division, setDivision] = useState("J&J Innovative Medicine");
  const [job, setJob] = useState<ExpandJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<number | null>(null);

  useEffect(() => () => {
    if (timer.current) window.clearInterval(timer.current);
  }, []);

  const start = async () => {
    setError(null);
    try {
      const j = await api.expand(name, division);
      setJob(j);
      if (timer.current) window.clearInterval(timer.current);
      timer.current = window.setInterval(async () => {
        try {
          const s = await api.expandStatus(j.job_id);
          setJob(s);
          if (s.status !== "running" && timer.current) {
            window.clearInterval(timer.current);
            timer.current = null;
            onGraphChanged();
          }
        } catch (e) {
          setError((e as Error).message);
          if (timer.current) window.clearInterval(timer.current);
        }
      }, 1500);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <div className="panel p-4">
      <div className="label-xs mb-3 flex items-center gap-1.5">
        <PlusCircle size={12} /> Expand portfolio · one product, all sources
      </div>
      <div className="grid grid-cols-[1fr_180px_auto] gap-2">
        <input className="input !py-1.5 text-xs" value={name} onChange={(e) => setName(e.target.value)} placeholder="Product name" />
        <select className="input !py-1.5 text-xs" value={division} onChange={(e) => setDivision(e.target.value)}>
          <option value="J&J Innovative Medicine">Innovative Medicine</option>
          <option value="J&J MedTech">MedTech</option>
        </select>
        <button className="btn-primary !py-1.5 text-xs" disabled={!name.trim() || job?.status === "running"} onClick={start}>
          {job?.status === "running" ? <Loader2 size={12} className="animate-spin" /> : <PlusCircle size={12} />} Expand
        </button>
      </div>
      {error && <div className="mt-2 text-xs text-red-300">{error}</div>}
      {job && (
        <div className="mt-3 space-y-1 text-xs">
          <div className="text-slate-400">
            Job <span className="font-mono">{job.job_id}</span> · <span className="text-white">{job.status}</span>
            {job.phase1?.product_id && (
              <>
                {" "}
                · product <span className="font-mono text-clinical">{job.phase1.product_id}</span> ({job.phase1.method})
              </>
            )}
          </div>
          {job.steps.map((s) => (
            <div key={s.step} className="flex items-center gap-2">
              {s.status === "running" ? (
                <Loader2 size={11} className="animate-spin text-clinical" />
              ) : s.status === "ok" || s.status === "complete" ? (
                <CheckCircle2 size={11} className="text-emerald-400" />
              ) : (
                <ShieldAlert size={11} className="text-amber-400" />
              )}
              <span className="w-40 font-mono text-slate-300">{s.step}</span>
              <span className="text-slate-500">{s.status}</span>
              <span className="text-slate-500">
                +{s.added_nodes}n / +{s.added_edges}e
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function UsagePanel() {
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [audit, setAudit] = useState<{ valid: boolean; entries: number; broken_at?: number | null } | null>(null);
  const [prompts, setPrompts] = useState<{ name: string; version: string }[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api.usage().then(setUsage).catch((e) => setError((e as Error).message));
    api.auditVerify().then(setAudit).catch(() => undefined);
    api.prompts().then(setPrompts).catch(() => undefined);
  }, []);
  useEffect(load, [load]);

  return (
    <div className="panel p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="label-xs flex items-center gap-1.5">
          <Activity size={12} /> Usage, quality &amp; governance
        </div>
        <button className="btn-ghost !py-1 text-xs" onClick={load}>
          <RefreshCw size={12} /> Reload
        </button>
      </div>
      {error && <div className="text-xs text-red-300">{error}</div>}
      {usage && (
        <>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            <Stat label="Queries" value={usage.queries} sub={`${usage.unique_users} user(s)`} />
            <Stat label="Avg latency" value={`${Math.round(usage.avg_latency_ms)} ms`} />
            <Stat label="Avg confidence" value={`${Math.round((usage.avg_confidence ?? 0) * 100)}%`} />
            <Stat
              label="Satisfaction"
              value={usage.feedback.satisfaction_pct == null ? "—" : `${usage.feedback.satisfaction_pct}%`}
              sub={`${usage.feedback.positive}/${usage.feedback.total} thumbs up`}
            />
            <Stat label="MLR reviews" value={usage.mlr_reviews} sub={usage.mlr_decisions.map((d) => `${d.n} ${d.decision}`).join(" · ") || "no decisions"} />
            <Stat label="LLM cost" value={`$${usage.llm_cost_usd.toFixed(4)}`} sub={`${usage.llm_usage.reduce((a, b) => a + b.calls, 0)} calls`} />
            <Stat label="Tool calls" value={usage.tool_calls.reduce((a, b) => a + b.n, 0)} sub={`${usage.tool_calls.reduce((a, b) => a + b.errors, 0)} errors`} />
            <Stat
              label="Audit chain"
              value={audit ? (audit.valid ? "intact" : "BROKEN") : "—"}
              sub={audit ? `${audit.entries} entries${audit.broken_at ? ` · broken at ${audit.broken_at}` : ""}` : undefined}
            />
          </div>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <div>
              <div className="label-xs mb-1.5">Queries by agent</div>
              <Bars rows={usage.by_agent.map((r) => ({ k: r.routed_agent ?? "—", n: r.n }))} />
            </div>
            <div>
              <div className="label-xs mb-1.5">Queries by risk level</div>
              <Bars rows={usage.by_risk.map((r) => ({ k: r.risk_level ?? "—", n: r.n }))} />
            </div>
            <div>
              <div className="label-xs mb-1.5">External tool calls</div>
              <Bars rows={usage.tool_calls.map((r) => ({ k: `${r.tool} (${Math.round(r.avg_ms)}ms)`, n: r.n }))} />
            </div>
            <div>
              <div className="label-xs mb-1.5 flex items-center gap-1">
                <ScrollText size={11} /> Versioned prompts
              </div>
              <div className="flex flex-wrap gap-1">
                {prompts.map((p) => (
                  <span key={p.name} className="pill !py-0 border-slate-700 font-mono text-[10px] text-slate-400">
                    {p.name}@{p.version}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function EvalPanel() {
  const [res, setRes] = useState<EvalSummary | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      setRes(await api.runEval());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const metricKeys = res ? Array.from(new Set(Object.values(res.methods).flatMap((m) => Object.keys(m)))) : [];
  return (
    <div className="panel p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="label-xs flex items-center gap-1.5">
          <FlaskConical size={12} /> Retrieval &amp; answer evaluation (golden set)
        </div>
        <button className="btn-primary !py-1 text-xs" disabled={busy} onClick={run}>
          {busy ? <Loader2 size={12} className="animate-spin" /> : <BarChart3 size={12} />} Run eval
        </button>
      </div>
      {error && <div className="text-xs text-red-300">{error}</div>}
      {!res && !busy && <div className="text-xs text-slate-500">Runs the 40-query golden set comparing GraphRAG against BM25, dense and hybrid baselines.</div>}
      {res && (
        <>
          <table className="w-full text-left text-xs">
            <thead className="text-slate-500">
              <tr>
                <th className="py-1">Method</th>
                {metricKeys.map((k) => (
                  <th key={k} className="py-1 text-right">
                    {k}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Object.entries(res.methods).map(([m, vals]) => (
                <tr key={m} className={`border-t border-slate-800/80 ${m === "graphrag" ? "text-clinical" : "text-slate-300"}`}>
                  <td className="py-1.5 font-semibold">{m}</td>
                  {metricKeys.map((k) => (
                    <td key={k} className="py-1.5 text-right font-mono">
                      {vals[k] != null ? vals[k].toFixed(3) : "—"}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4">
            <Stat label="Routing accuracy" value={res.routing_accuracy.toFixed(3)} />
            <Stat label="Citation precision" value={res.citation_precision.toFixed(3)} />
            <Stat label="Groundedness" value={res.groundedness != null ? res.groundedness.toFixed(3) : "—"} />
            <Stat label="Answer entity hit" value={res.answer_entity_hit != null ? res.answer_entity_hit.toFixed(3) : "—"} />
          </div>
          <div className="mt-2 text-[11px] text-slate-500">
            n={res.n}, k={res.k} · dense: {res.dense_method} · reranker: {res.reranker} · {res.elapsed_s}s · {res.failures.length} failure(s)
          </div>
          {res.failures.length > 0 && (
            <details className="mt-2 text-[11px] text-slate-400">
              <summary className="cursor-pointer">Failures</summary>
              <ul className="mt-1 space-y-1">
                {res.failures.map((f) => (
                  <li key={f.id}>
                    <span className="font-mono">{f.id}</span> {f.query} — expected {f.expected.join(", ")}, got {f.got_top.slice(0, 3).join(", ")}
                    {f.expected_agent !== f.routed ? ` · routed ${f.routed} (expected ${f.expected_agent})` : ""}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </>
      )}
    </div>
  );
}

export default function OpsDashboard({ onGraphChanged }: { onGraphChanged: () => void }) {
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <div className="space-y-4">
        <SourcesPanel onGraphChanged={onGraphChanged} />
        <ExpandPanel onGraphChanged={onGraphChanged} />
      </div>
      <div className="space-y-4">
        <UsagePanel />
        <EvalPanel />
        <div className="flex items-center gap-1.5 px-1 text-[11px] text-slate-500">
          <ThumbsUp size={11} /> Feedback from the Agent Copilot feeds the satisfaction metric above.
        </div>
      </div>
    </div>
  );
}
