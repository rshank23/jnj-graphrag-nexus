import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertOctagon,
  AlertTriangle,
  BookCheck,
  CheckCircle2,
  ClipboardCheck,
  Download,
  FileSearch,
  Gavel,
  History,
  Info,
  Loader2,
  PenLine,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { api, session } from "../api/client";
import type { MLRClaim, MLRFinding, MLRReview, MLRReviewListItem, Severity } from "../types/graph";

const SAMPLES = [
  {
    tag: "Non-compliant draft",
    title: "TREMFYA HCP email (draft v1)",
    text:
      "TREMFYA cures psoriasis completely with no side effects. TREMFYA is proven superior to every other biologic. " +
      "TREMFYA is also effective for multiple myeloma. Pair TREMFYA with the CARTO 3 System V8 for best results.",
  },
  {
    tag: "Safety omitted",
    title: "CARVYKTI banner ad",
    text: "CARVYKTI delivers deep and durable responses for patients with relapsed or refractory multiple myeloma. Ask about CARVYKTI today.",
  },
  {
    tag: "Compliant copy",
    title: "CARVYKTI indication statement",
    text:
      "CARVYKTI is indicated for adult patients with relapsed or refractory multiple myeloma after prior lines of therapy. " +
      "See full Prescribing Information, including Boxed Warning for cytokine release syndrome and neurologic toxicities.",
  },
];

const SEV_ORDER: Severity[] = ["critical", "warning", "unverified", "info"];
const SEV_STYLE: Record<Severity, { pill: string; mark: string; icon: typeof AlertOctagon }> = {
  critical: { pill: "border-red-700 bg-red-950/50 text-red-300", mark: "bg-red-500/25 border-b-2 border-red-500", icon: AlertOctagon },
  warning: { pill: "border-amber-700 bg-amber-950/50 text-amber-300", mark: "bg-amber-400/20 border-b-2 border-amber-400", icon: AlertTriangle },
  unverified: { pill: "border-sky-700 bg-sky-950/50 text-sky-300", mark: "bg-sky-400/15 border-b-2 border-sky-400", icon: FileSearch },
  info: { pill: "border-slate-600 bg-slate-800/60 text-slate-300", mark: "bg-slate-500/15 border-b border-slate-400", icon: Info },
};
const STATUS_STYLE: Record<string, string> = {
  "not-ready": "border-red-700 bg-red-950/50 text-red-200",
  "needs-review": "border-amber-700 bg-amber-950/50 text-amber-200",
  "ready-for-mlr": "border-emerald-700 bg-emerald-950/50 text-emerald-200",
};
const VERDICT_STYLE: Record<string, string> = {
  supported: "text-emerald-300",
  partial: "text-amber-300",
  unsupported: "text-orange-300",
  contradicted: "text-red-300",
  no_evidence: "text-slate-400",
};

function worstSeverity(findings: MLRFinding[]): Severity | null {
  for (const s of SEV_ORDER) if (findings.some((f) => f.severity === s)) return s;
  return null;
}

function HighlightedAsset({
  review,
  selected,
  onSelect,
}: {
  review: MLRReview;
  selected: string | null;
  onSelect: (claimId: string | null) => void;
}) {
  const parts = useMemo(() => {
    const text = review.asset_text;
    const claims = [...review.claims].filter((c) => c.end > c.start).sort((a, b) => a.start - b.start);
    const out: { text: string; claim?: MLRClaim }[] = [];
    let pos = 0;
    for (const c of claims) {
      if (c.start < pos) continue;
      if (c.start > pos) out.push({ text: text.slice(pos, c.start) });
      out.push({ text: text.slice(c.start, c.end), claim: c });
      pos = c.end;
    }
    if (pos < text.length) out.push({ text: text.slice(pos) });
    return out;
  }, [review]);

  return (
    <p className="whitespace-pre-wrap text-sm leading-7 text-slate-200">
      {parts.map((p, i) => {
        if (!p.claim) return <span key={i}>{p.text}</span>;
        const sev = worstSeverity(review.findings.filter((f) => f.claim_id === p.claim!.id));
        const cls = sev ? SEV_STYLE[sev].mark : "bg-emerald-500/10 border-b border-emerald-500/60";
        return (
          <mark
            key={i}
            onClick={() => onSelect(selected === p.claim!.id ? null : p.claim!.id)}
            className={`cursor-pointer rounded-sm px-0.5 text-inherit transition ${cls} ${selected === p.claim.id ? "ring-2 ring-clinical" : ""}`}
            title={`${p.claim.id} · ${p.claim.verdict} · ${p.claim.claim_types.join(", ")}`}
          >
            {p.text}
          </mark>
        );
      })}
    </p>
  );
}

function FindingCard({ f, onDecide, busy }: { f: MLRFinding; onDecide: (f: MLRFinding, d: "accepted" | "rejected" | "revision") => void; busy: boolean }) {
  const style = SEV_STYLE[f.severity] ?? SEV_STYLE.info;
  const Icon = style.icon;
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-start gap-2">
          <Icon size={15} className="mt-0.5 shrink-0" />
          <div>
            <div className="text-sm font-semibold text-slate-100">{f.title}</div>
            <div className="mt-0.5 flex flex-wrap gap-1 text-[10px]">
              <span className={`pill !py-0 ${style.pill}`}>{f.severity}</span>
              <span className="pill !py-0 border-slate-700 text-slate-400">{f.check.replace(/_/g, " ")}</span>
              {f.claim_id && <span className="pill !py-0 border-slate-700 font-mono text-slate-400">{f.claim_id}</span>}
              <span className="pill !py-0 border-slate-700 font-mono text-slate-500">{f.id}</span>
            </div>
          </div>
        </div>
        {f.decision && (
          <span
            className={`pill shrink-0 text-[10px] ${
              f.decision.decision === "accepted" ? "border-emerald-700 text-emerald-300" : f.decision.decision === "rejected" ? "border-slate-600 text-slate-400" : "border-amber-700 text-amber-300"
            }`}
            title={`${f.decision.reviewer ?? ""} · ${f.decision.ts}${f.decision.rationale ? ` · ${f.decision.rationale}` : ""}`}
          >
            {f.decision.decision}
          </span>
        )}
      </div>
      <p className="mt-2 text-xs leading-relaxed text-slate-300">{f.detail}</p>
      {f.suggestion && (
        <p className="mt-2 rounded border border-emerald-900/60 bg-emerald-950/20 px-2 py-1.5 text-xs text-emerald-200">
          <PenLine size={11} className="mr-1 inline" />
          {f.suggestion}
        </p>
      )}
      {(f.evidence.length > 0 || f.precedents.length > 0) && (
        <details className="mt-2">
          <summary className="cursor-pointer text-[11px] text-slate-500">
            {f.evidence.length} evidence · {f.precedents.length} regulatory precedent{f.precedents.length === 1 ? "" : "s"}
          </summary>
          <ul className="mt-1.5 space-y-1 text-[11px] text-slate-400">
            {f.evidence.map((e, i) => (
              <li key={`e${i}`}>
                <FileSearch size={10} className="mr-1 inline text-clinical" />
                {e.source_url ? (
                  <a className="underline decoration-dotted hover:text-clinical" href={String(e.source_url)} target="_blank" rel="noreferrer">
                    {String(e.name ?? e.node_id ?? "evidence")}
                  </a>
                ) : (
                  String(e.name ?? e.node_id ?? e.text ?? "evidence")
                )}
                {e.published ? <span className="text-slate-600"> · {String(e.published)}</span> : null}
              </li>
            ))}
            {f.precedents.map((p, i) => (
              <li key={`p${i}`}>
                <Gavel size={10} className="mr-1 inline text-amber-400" />
                <span className="text-slate-300">{p.category}</span> — {p.summary} <span className="text-slate-500">({p.regulation})</span>
              </li>
            ))}
          </ul>
        </details>
      )}
      <div className="mt-2 flex gap-1.5">
        {(
          [
            ["accepted", "Accept", CheckCircle2, "hover:border-emerald-600 hover:text-emerald-300"],
            ["revision", "Needs revision", PenLine, "hover:border-amber-600 hover:text-amber-300"],
            ["rejected", "Dismiss", XCircle, "hover:border-slate-500 hover:text-slate-200"],
          ] as const
        ).map(([d, label, I, cls]) => (
          <button
            key={d}
            disabled={busy}
            onClick={() => onDecide(f, d)}
            className={`flex items-center gap-1 rounded border border-slate-700 px-2 py-1 text-[11px] text-slate-400 transition disabled:opacity-50 ${cls}`}
          >
            <I size={11} /> {label}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function MLRReviewPanel() {
  const [title, setTitle] = useState(SAMPLES[0].title);
  const [text, setText] = useState(SAMPLES[0].text);
  const [useLlm, setUseLlm] = useState(true);
  const [running, setRunning] = useState(false);
  const [busy, setBusy] = useState(false);
  const [review, setReview] = useState<MLRReview | null>(null);
  const [history, setHistory] = useState<MLRReviewListItem[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadHistory = useCallback(() => {
    api.mlrReviews().then(setHistory).catch(() => undefined);
  }, []);
  useEffect(loadHistory, [loadHistory]);

  const run = async () => {
    if (text.trim().length < 10 || running) return;
    setRunning(true);
    setError(null);
    setNotice(null);
    setSelected(null);
    try {
      setReview(await api.mlrReview(text, title, useLlm));
      loadHistory();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRunning(false);
    }
  };

  const open = async (id: string) => {
    setError(null);
    setSelected(null);
    try {
      const r = await api.mlrGet(id);
      setReview(r);
      setTitle(r.title);
      setText(r.asset_text);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const decide = async (f: MLRFinding, d: "accepted" | "rejected" | "revision") => {
    if (!review) return;
    const rationale = d === "accepted" ? undefined : window.prompt(`Rationale for '${d}' on ${f.id} (optional)`) ?? undefined;
    setBusy(true);
    setError(null);
    try {
      await api.mlrDecide(review.review_id, f.id, d, rationale);
      setReview(await api.mlrGet(review.review_id));
      loadHistory();
    } catch (e) {
      setError(`${(e as Error).message}${session.role() === "commercial" ? " — switch role to MLR or Medical in the header." : ""}`);
    } finally {
      setBusy(false);
    }
  };

  const approve = async (c: MLRClaim) => {
    if (!review) return;
    setBusy(true);
    setError(null);
    try {
      await api.mlrApproveClaim(review.review_id, c.id);
      setNotice(`Claim ${c.id} added to the approved claims library — future assets reuse this decision.`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const visibleFindings = useMemo(() => {
    if (!review) return [];
    const list = selected ? review.findings.filter((f) => f.claim_id === selected) : review.findings;
    return [...list].sort((a, b) => SEV_ORDER.indexOf(a.severity) - SEV_ORDER.indexOf(b.severity));
  }, [review, selected]);

  const decided = review?.findings.filter((f) => f.decision).length ?? 0;

  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_480px]">
      <div className="space-y-4">
        <div className="panel p-4">
          <div className="mb-2 flex items-center justify-between">
            <div className="label-xs flex items-center gap-1.5">
              <ClipboardCheck size={12} /> Promotional asset for MLR pre-review
            </div>
            <div className="flex gap-1.5">
              {SAMPLES.map((s) => (
                <button
                  key={s.tag}
                  onClick={() => {
                    setTitle(s.title);
                    setText(s.text);
                  }}
                  className="rounded border border-slate-800 px-2 py-0.5 text-[11px] text-slate-400 hover:border-slate-600 hover:text-white"
                >
                  {s.tag}
                </button>
              ))}
            </div>
          </div>
          <input className="input mb-2" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Asset title" />
          <textarea
            className="input min-h-[140px] font-mono text-xs leading-relaxed"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Paste email / detail-aid / banner copy…"
          />
          <div className="mt-2 flex items-center justify-between gap-3">
            <label className="flex items-center gap-2 text-xs text-slate-400">
              <input type="checkbox" checked={useLlm} onChange={(e) => setUseLlm(e.target.checked)} />
              LLM-assisted claim extraction (falls back to rules when no model is configured)
            </label>
            <button className="btn-primary" disabled={running || text.trim().length < 10} onClick={run}>
              {running ? <Loader2 size={15} className="animate-spin" /> : <ShieldCheck size={15} />} Run pre-review
            </button>
          </div>
        </div>

        {error && <div className="rounded-lg border border-red-900 bg-red-950/40 px-4 py-2 text-sm text-red-300">{error}</div>}
        {notice && <div className="rounded-lg border border-emerald-900 bg-emerald-950/30 px-4 py-2 text-sm text-emerald-300">{notice}</div>}

        {review && (
          <div className="panel p-5">
            <div className="mb-4 flex flex-wrap items-center gap-2">
              <span className={`pill text-xs font-semibold uppercase ${STATUS_STYLE[review.summary.status] ?? ""}`}>{review.summary.status.replace(/-/g, " ")}</span>
              <span className="pill border-slate-700 text-xs text-slate-300">risk score {review.summary.risk_score}</span>
              {SEV_ORDER.map((s) =>
                review.summary.severity_counts[s] ? (
                  <span key={s} className={`pill text-xs ${SEV_STYLE[s].pill}`}>
                    {review.summary.severity_counts[s]} {s}
                  </span>
                ) : null,
              )}
              <span className="pill border-slate-700 text-xs text-slate-400">
                {review.summary.claims} claims · {review.summary.library_matches} library matches
              </span>
              <span className="pill border-slate-700 text-xs text-slate-400">
                {decided}/{review.findings.length} findings decided
              </span>
              <span className="flex-1" />
              <button className="btn-ghost !py-1 text-xs" onClick={() => api.mlrExport(review.review_id).catch((e) => setError((e as Error).message))}>
                <Download size={13} /> Export DOCX
              </button>
            </div>
            <div className="label-xs mb-2">Annotated asset · click a highlighted claim to filter findings</div>
            <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
              <HighlightedAsset review={review} selected={selected} onSelect={setSelected} />
            </div>

            <div className="label-xs mb-2 mt-5">Claim verification</div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="text-slate-500">
                  <tr>
                    <th className="py-1 pr-2">ID</th>
                    <th className="py-1 pr-2">Claim</th>
                    <th className="py-1 pr-2">Type</th>
                    <th className="py-1 pr-2">Verdict</th>
                    <th className="py-1 pr-2">Conf.</th>
                    <th className="py-1" />
                  </tr>
                </thead>
                <tbody>
                  {review.claims.map((c) => (
                    <tr
                      key={c.id}
                      className={`cursor-pointer border-t border-slate-800/80 hover:bg-slate-800/30 ${selected === c.id ? "bg-clinical/10" : ""}`}
                      onClick={() => setSelected(selected === c.id ? null : c.id)}
                    >
                      <td className="py-1.5 pr-2 font-mono text-slate-500">{c.id}</td>
                      <td className="py-1.5 pr-2 text-slate-300">{c.text}</td>
                      <td className="py-1.5 pr-2 text-slate-400">{c.claim_types.join(", ")}</td>
                      <td className={`py-1.5 pr-2 font-semibold ${VERDICT_STYLE[c.verdict] ?? "text-slate-300"}`}>
                        {c.verdict.replace(/_/g, " ")}
                        {c.library_match ? <BookCheck size={11} className="ml-1 inline text-emerald-400" /> : null}
                      </td>
                      <td className="py-1.5 pr-2 font-mono text-slate-400">{(c.confidence * 100).toFixed(0)}%</td>
                      <td className="py-1.5 text-right">
                        <button
                          disabled={busy || c.finding_ids.length > 0}
                          title={c.finding_ids.length ? "Resolve findings before approving" : "Approve into the claims library"}
                          onClick={(e) => {
                            e.stopPropagation();
                            approve(c);
                          }}
                          className="rounded border border-slate-700 px-1.5 py-0.5 text-[10px] text-slate-400 hover:border-emerald-600 hover:text-emerald-300 disabled:opacity-30"
                        >
                          approve
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-4 text-[11px] italic text-slate-500">{review.disclaimer}</p>
          </div>
        )}
        {!review && !running && (
          <div className="panel flex flex-col items-center justify-center gap-2 p-10 text-center text-sm text-slate-500">
            <ClipboardCheck size={28} className="text-slate-600" />
            Paste promotional copy and run a pre-review: claims are extracted, verified against FDA labels and evidence in the graph, and checked
            for off-label, comparative, absolute, safety-omission and cross-product issues before the asset reaches the MLR committee.
          </div>
        )}
      </div>

      <div className="space-y-4">
        <div className="panel p-4">
          <div className="mb-2 flex items-center justify-between">
            <div className="label-xs">Findings {selected && <span className="text-clinical">· {selected}</span>}</div>
            {selected && (
              <button className="text-[11px] text-slate-500 hover:text-white" onClick={() => setSelected(null)}>
                show all
              </button>
            )}
          </div>
          {!review && <div className="text-xs text-slate-500">Findings appear after a review runs.</div>}
          {review && visibleFindings.length === 0 && (
            <div className="flex items-center gap-2 text-xs text-emerald-300">
              <CheckCircle2 size={14} /> No findings{selected ? " for this claim" : ""}.
            </div>
          )}
          <div className="max-h-[720px] space-y-2 overflow-y-auto pr-1">
            {visibleFindings.map((f) => (
              <FindingCard key={f.id} f={f} onDecide={decide} busy={busy} />
            ))}
          </div>
        </div>
        <div className="panel p-4">
          <div className="label-xs mb-2 flex items-center gap-1.5">
            <History size={12} /> Recent reviews
          </div>
          {history.length === 0 && <div className="text-xs text-slate-500">No reviews yet.</div>}
          <ul className="space-y-1">
            {history.slice(0, 10).map((h) => (
              <li key={h.review_id}>
                <button
                  onClick={() => open(h.review_id)}
                  className={`flex w-full items-center justify-between gap-2 rounded px-2 py-1.5 text-left text-xs hover:bg-slate-800/60 ${
                    review?.review_id === h.review_id ? "bg-slate-800/60" : ""
                  }`}
                >
                  <span className="truncate text-slate-300">{h.title}</span>
                  <span className="flex shrink-0 items-center gap-1.5">
                    <span className="text-slate-500">
                      {h.decided}/{h.findings}
                    </span>
                    <span className={`pill !px-1.5 !py-0 text-[10px] ${STATUS_STYLE[h.summary.status] ?? ""}`}>{h.summary.status}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
