import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Bot, CheckCircle2, Circle, FileCheck2, GitMerge, Loader2, Network, Route, Search, Send, Sparkles, Timer } from "lucide-react";
import { api } from "../api/client";
import type { AgentQueryResponse } from "../types/graph";
import { ForceGraphCanvas } from "./GraphExplorer";

const PRESETS = [
  {
    tag: "MedTech Bundler",
    query:
      "Build a complete end-to-end J&J MedTech procedural bundle for Atrial Fibrillation ablation including 3D CT segmentation modules and post-op infection control.",
  },
  {
    tag: "Pharma Clinical",
    query: "How do OPSYNVI, OPSUMIT, and UPTRAVI work together across PAH biological pathways, and what are the strict contraindications?",
  },
  {
    tag: "Regulatory Auditor",
    query: "Audit the clinical efficacy claims and 2026 trial data for ICOTYDE, RYBREVANT FASPRO, and CARVYKTI with FDA label provenance.",
  },
  {
    tag: "Software & Couplings",
    query:
      "Which J&J MedTech software modules segment 3D CT cardiac anatomy and which saw blades are cross-compatible with competitor couplings?",
  },
];

const STEPS = [
  { key: "Supervisor Router", icon: Route },
  { key: "Hybrid BM25+Vector Search", icon: Search },
  { key: "2-Hop Graph Expansion", icon: Network },
  { key: "Cross-Encoder Reranker", icon: GitMerge },
  { key: "Domain Sub-Agent", icon: Bot },
];

const AGENT_LABEL: Record<string, string> = {
  medtech_bundler: "MedTech Bundler Agent",
  pharma_clinical: "Pharma Clinical Agent",
  regulatory_auditor: "Regulatory Auditor Agent",
};

export default function AgentCopilot() {
  const [query, setQuery] = useState(PRESETS[0].query);
  const [running, setRunning] = useState(false);
  const [activeStep, setActiveStep] = useState(-1);
  const [result, setResult] = useState<AgentQueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<number | null>(null);

  useEffect(
    () => () => {
      if (timer.current) window.clearInterval(timer.current);
    },
    [],
  );

  const run = async (q: string) => {
    const text = q.trim();
    if (text.length < 2 || running) return;
    setQuery(text);
    setRunning(true);
    setError(null);
    setResult(null);
    setActiveStep(0);
    // Animate the pipeline while the request is in flight; the real trace replaces it on completion.
    timer.current = window.setInterval(() => setActiveStep((s) => Math.min(s + 1, STEPS.length - 1)), 350);
    try {
      const res = await api.agentQuery(text, 6, 2);
      setResult(res);
      setActiveStep(STEPS.length);
    } catch (e) {
      setError((e as Error).message);
      setActiveStep(-1);
    } finally {
      if (timer.current) window.clearInterval(timer.current);
      timer.current = null;
      setRunning(false);
    }
  };

  const traceFor = (key: string) => result?.execution_trace.find((t) => t.startsWith(key));

  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_420px]">
      <div className="space-y-4">
        {/* Presets + input */}
        <div className="panel p-4">
          <div className="label-xs mb-2 flex items-center gap-1.5">
            <Sparkles size={12} /> One-click enterprise queries
          </div>
          <div className="grid gap-2 md:grid-cols-2">
            {PRESETS.map((p) => (
              <button
                key={p.tag}
                disabled={running}
                onClick={() => run(p.query)}
                className={`rounded-lg border p-3 text-left text-xs leading-snug transition disabled:opacity-50 ${
                  query === p.query ? "border-clinical/70 bg-clinical/5 text-slate-100" : "border-slate-800 bg-slate-950/40 text-slate-400 hover:border-slate-600"
                }`}
              >
                <div className="mb-1 font-semibold uppercase tracking-wide text-clinical">{p.tag}</div>
                {p.query}
              </button>
            ))}
          </div>
          <form
            className="mt-3 flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              run(query);
            }}
          >
            <input className="input" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Ask about bundles, pathways, claims, couplings…" />
            <button type="submit" className="btn-primary shrink-0" disabled={running || query.trim().length < 2}>
              {running ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />} Run
            </button>
          </form>
        </div>

        {/* Pipeline stepper */}
        <div className="panel p-4">
          <div className="mb-3 flex items-center justify-between">
            <div className="label-xs">LangGraph Execution Pipeline</div>
            {result && (
              <div className="flex items-center gap-3 text-xs text-slate-400">
                <span className="pill border-jnj/60 bg-jnj/10 text-white">
                  <Bot size={12} /> {AGENT_LABEL[result.routed_agent] ?? result.routed_agent}
                </span>
                <span className="flex items-center gap-1">
                  <Timer size={12} /> {result.latency_ms.toFixed(0)} ms
                </span>
              </div>
            )}
          </div>
          <ol className="grid gap-2 md:grid-cols-5">
            {STEPS.map((s, i) => {
              const done = activeStep > i;
              const active = activeStep === i && running;
              const Icon = s.icon;
              const detail = traceFor(s.key);
              return (
                <li
                  key={s.key}
                  title={detail}
                  className={`relative rounded-lg border p-2.5 transition ${
                    done ? "border-emerald-700/70 bg-emerald-950/30" : active ? "border-clinical bg-clinical/10" : "border-slate-800 bg-slate-950/40"
                  }`}
                >
                  <div className="flex items-center gap-1.5">
                    {done ? (
                      <CheckCircle2 size={14} className="text-emerald-400" />
                    ) : active ? (
                      <Loader2 size={14} className="animate-spin text-clinical" />
                    ) : (
                      <Circle size={14} className="text-slate-600" />
                    )}
                    <Icon size={13} className="text-slate-400" />
                  </div>
                  <div className="mt-1 text-[11px] font-semibold leading-tight text-slate-200">{s.key}</div>
                  {detail && <div className="mt-1 line-clamp-3 text-[10px] leading-snug text-slate-500">{detail.split(":").slice(1).join(":").trim() || detail}</div>}
                </li>
              );
            })}
          </ol>
          {result && (
            <details className="mt-3">
              <summary className="label-xs cursor-pointer">Full execution trace ({result.execution_trace.length} steps)</summary>
              <ol className="mt-2 space-y-1 font-mono text-[11px] text-slate-400">
                {result.execution_trace.map((t, i) => (
                  <li key={i}>
                    <span className="text-clinical">{String(i + 1).padStart(2, "0")}</span> {t}
                  </li>
                ))}
              </ol>
            </details>
          )}
        </div>

        {error && <div className="rounded-lg border border-red-900 bg-red-950/40 px-4 py-2 text-sm text-red-300">{error}</div>}

        {/* Answer */}
        {result && (
          <div className="panel p-5">
            <div className="markdown">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.answer_markdown}</ReactMarkdown>
            </div>
            {result.citations.length > 0 && (
              <div className="mt-4 border-t border-slate-800 pt-3">
                <div className="label-xs mb-2 flex items-center gap-1.5">
                  <FileCheck2 size={12} /> Citations
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {result.citations.map((c, i) => {
                    const inner = (
                      <>
                        <span className="font-mono text-clinical">[{i + 1}]</span> {c.title}
                        {c.doc_type && <span className="text-slate-500">· {c.doc_type}</span>}
                        {c.windchill_id && <span className="text-amber-300">· Windchill {c.windchill_id}</span>}
                      </>
                    );
                    return c.source_url ? (
                      <a
                        key={c.id}
                        href={c.source_url}
                        target="_blank"
                        rel="noreferrer"
                        className="pill border-slate-700 bg-slate-800/50 text-slate-300 hover:border-clinical"
                      >
                        {inner}
                      </a>
                    ) : (
                      <span key={c.id} className="pill border-slate-700 bg-slate-800/50 text-slate-300">
                        {inner}
                      </span>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}
        {!result && !running && !error && (
          <div className="panel flex flex-col items-center justify-center gap-2 p-10 text-center text-sm text-slate-500">
            <Bot size={28} className="text-slate-600" />
            Pick a preset or ask your own question to run the supervisor → hybrid retrieval → specialist-agent pipeline.
          </div>
        )}
      </div>

      {/* Right column: scores + subgraph */}
      <div className="space-y-4">
        <div className="panel p-4">
          <div className="label-xs mb-2">Cross-Encoder Reranked Evidence</div>
          {!result && <div className="text-xs text-slate-500">Scores appear after a query runs.</div>}
          <div className="space-y-2">
            {result?.reranked_passages.map((p) => (
              <div key={p.id} className="rounded-lg border border-slate-800 bg-slate-950/50 p-2.5">
                <div className="mb-1 flex items-center justify-between gap-2">
                  <span className={`pill !px-1.5 !py-0 text-[10px] ${p.type === "graph_path" ? "border-violet-700 text-violet-300" : "border-cyan-800 text-cyan-300"}`}>
                    {p.type === "graph_path" ? `graph path · hop ${p.hop}` : `passage · hop ${p.hop}`}
                  </span>
                  <span className="font-mono text-xs text-white">{p.cross_encoder_score.toFixed(3)}</span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-slate-800">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-clinical to-emerald-400"
                    style={{ width: `${Math.max(4, Math.min(100, p.cross_encoder_score * 100))}%` }}
                  />
                </div>
                <p className="mt-1.5 line-clamp-3 text-[11px] leading-snug text-slate-400">{p.text}</p>
              </div>
            ))}
          </div>
        </div>
        {result && result.subgraph.nodes.length > 0 && (
          <div className="panel overflow-hidden">
            <div className="label-xs px-4 pt-3">
              Retrieved subgraph ({result.subgraph.nodes.length} nodes · {result.subgraph.links.length} edges)
            </div>
            <div className="h-[340px]">
              <ForceGraphCanvas nodes={result.subgraph.nodes} links={result.subgraph.links} showLegend={false} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
