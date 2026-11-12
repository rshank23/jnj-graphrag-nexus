import { useState } from "react";
import { AlertOctagon, CheckCircle2, FileUp, Globe, Link2, Loader2, Pill, ShieldCheck, Type, X } from "lucide-react";
import { api } from "../api/client";
import type { EvidenceMode, IngestMode, IngestResponse } from "../types/graph";

const EVIDENCE: { id: EvidenceMode; label: string; placeholder: string }[] = [
  { id: "openfda_label", label: "openFDA drug label (indications, boxed warning, label-change diff)", placeholder: "TREMFYA" },
  { id: "faers", label: "FAERS adverse events + PRR/ROR disproportionality signals", placeholder: "CARVYKTI" },
  { id: "drug_recalls", label: "openFDA drug enforcement / recalls", placeholder: "RISPERDAL" },
  { id: "device_recalls", label: "openFDA device recalls", placeholder: "ACUVUE" },
  { id: "gudid", label: "AccessGUDID device identifiers (UDI)", placeholder: "CARTO" },
  { id: "maude", label: "MAUDE device adverse events", placeholder: "VELYS" },
  { id: "clinicaltrials", label: "ClinicalTrials.gov studies", placeholder: "RYBREVANT" },
  { id: "pubmed", label: "PubMed publications", placeholder: "amivantamab" },
  { id: "expand", label: "Expand: run every applicable source for one product", placeholder: "SPRAVATO" },
];
const isEvidence = (m: IngestMode) => EVIDENCE.some((e) => e.id === m);

const MODES: { id: IngestMode; label: string; icon: typeof Globe; hint: string }[] = [
  { id: "live", label: "Live J&J Scrape", icon: Globe, hint: "Crawl jnj.com Innovative Medicine & MedTech product pages (Kenvue brands auto-rejected)." },
  { id: "dailymed", label: "FDA DailyMed", icon: Pill, hint: "Resolve the latest SPL label for a drug from NIH DailyMed and link it as evidence." },
  { id: "url", label: "Product URL", icon: Link2, hint: "Scrape a single jnj.com / jnjmedtech.com / DailyMed page." },
  { id: "text", label: "Custom Text", icon: Type, hint: "Paste a product description or label excerpt to extract entities." },
  { id: "pdf", label: "Label PDF", icon: FileUp, hint: "Upload an FDA prescribing-information PDF (boxed warnings, contraindications, indications)." },
  { id: "openfda_label", label: "Evidence APIs", icon: ShieldCheck, hint: "Pull regulatory & scientific evidence (openFDA, FAERS, recalls, GUDID, MAUDE, ClinicalTrials.gov, PubMed) into the graph with provenance." },
];

interface Props {
  open: boolean;
  onClose: () => void;
  onIngested: () => void;
}

export default function IngestionModal({ open, onClose, onIngested }: Props) {
  const [mode, setMode] = useState<IngestMode>("live");
  const [evMode, setEvMode] = useState<EvidenceMode>("openfda_label");
  const [drugName, setDrugName] = useState("CARVYKTI");
  const [url, setUrl] = useState("https://www.jnj.com/innovativemedicine");
  const [productName, setProductName] = useState("");
  const [productText, setProductText] = useState("");
  const [division, setDivision] = useState("J&J Innovative Medicine");
  const [franchise, setFranchise] = useState("");
  const [maxPages, setMaxPages] = useState(2);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<IngestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  const submit = async () => {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const fields =
        mode === "live"
          ? { max_pages: maxPages }
          : mode === "dailymed" || isEvidence(mode)
            ? { drug_name: drugName, division }
            : mode === "url"
              ? { url, division }
              : { product_name: productName || undefined, product_text: productText || undefined, division, franchise: franchise || undefined };
      const res = await api.ingest(mode, fields, mode === "pdf" ? file : null);
      setResult(res);
      if (res.added_nodes.length || res.added_edges.length) onIngested();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const canSubmit =
    !busy &&
    (mode === "live" ||
      ((mode === "dailymed" || isEvidence(mode)) && drugName.trim()) ||
      (mode === "url" && url.trim()) ||
      (mode === "text" && productText.trim()) ||
      (mode === "pdf" && file));

  const statusColor =
    result?.status === "rejected" ? "border-red-800 bg-red-950/40 text-red-300" : result?.status === "error" ? "border-amber-800 bg-amber-950/40 text-amber-300" : "border-emerald-800 bg-emerald-950/30 text-emerald-300";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#05070d]/85 p-4" onMouseDown={onClose}>
      <div className="panel max-h-[90vh] w-full max-w-2xl overflow-y-auto bg-slate-900 p-5 shadow-2xl" onMouseDown={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h2 className="display text-[28px] leading-tight">Knowledge Graph Ingestion</h2>
            <p className="text-xs text-slate-400">Sync live J&amp;J / FDA DailyMed sources or ingest custom labels. Kenvue consumer brands are always rejected.</p>
          </div>
          <button className="text-slate-500 hover:text-white" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className="mb-4 grid grid-cols-6 gap-1.5">
          {MODES.map((m) => {
            const Icon = m.icon;
            return (
              <button
                key={m.id}
                onClick={() => {
                  setMode(m.id === "openfda_label" ? evMode : m.id);
                  setResult(null);
                  setError(null);
                }}
                className={`flex flex-col items-center gap-1 rounded-lg border px-2 py-2.5 text-[11px] font-medium transition ${
                  (m.id === "openfda_label" ? isEvidence(mode) : mode === m.id) ? "border-jnj bg-jnj/15 text-white" : "border-slate-800 text-slate-400 hover:border-slate-600"
                }`}
              >
                <Icon size={16} />
                {m.label}
              </button>
            );
          })}
        </div>
        <p className="mb-4 text-xs text-slate-500">{MODES.find((m) => m.id === (isEvidence(mode) ? "openfda_label" : mode))?.hint}</p>

        <div className="space-y-3">
          {mode === "live" && (
            <div>
              <label className="label-xs">Max pages per division</label>
              <input type="number" min={1} max={10} className="input mt-1" value={maxPages} onChange={(e) => setMaxPages(Math.max(1, Math.min(10, Number(e.target.value) || 1)))} />
            </div>
          )}
          {isEvidence(mode) && (
            <div>
              <label className="label-xs">Evidence source</label>
              <select
                className="input mt-1"
                value={mode}
                onChange={(e) => {
                  const v = e.target.value as EvidenceMode;
                  setEvMode(v);
                  setMode(v);
                  setDrugName(EVIDENCE.find((x) => x.id === v)?.placeholder ?? drugName);
                }}
              >
                {EVIDENCE.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.label}
                  </option>
                ))}
              </select>
            </div>
          )}
          {(mode === "dailymed" || isEvidence(mode)) && (
            <div>
              <label className="label-xs">Drug / brand name</label>
              <input className="input mt-1" value={drugName} onChange={(e) => setDrugName(e.target.value)} placeholder="e.g. CARVYKTI, OPSYNVI, Tylenol (will be rejected)" />
            </div>
          )}
          {mode === "url" && (
            <div>
              <label className="label-xs">Source URL</label>
              <input className="input mt-1" value={url} onChange={(e) => setUrl(e.target.value)} />
            </div>
          )}
          {(mode === "text" || mode === "pdf") && (
            <div>
              <label className="label-xs">Product name (optional — auto-detected)</label>
              <input className="input mt-1" value={productName} onChange={(e) => setProductName(e.target.value)} placeholder="e.g. NEWDRUG (newgeneric)" />
            </div>
          )}
          {mode === "text" && (
            <div>
              <label className="label-xs">Product / label text</label>
              <textarea
                className="input mt-1 h-32 font-mono text-xs"
                value={productText}
                onChange={(e) => setProductText(e.target.value)}
                placeholder={"INDICATIONS AND USAGE: ...\nWARNING: ...\nCONTRAINDICATIONS: ..."}
              />
            </div>
          )}
          {mode === "pdf" && (
            <div>
              <label className="label-xs">Prescribing-information PDF</label>
              <input
                type="file"
                accept="application/pdf,.pdf"
                className="mt-1 block w-full text-xs text-slate-400 file:mr-3 file:rounded-md file:border-0 file:bg-slate-800 file:px-3 file:py-1.5 file:text-slate-200"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </div>
          )}
          {mode !== "live" && mode !== "dailymed" && (!isEvidence(mode) || mode === "expand") && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label-xs">Division</label>
                <select className="input mt-1" value={division} onChange={(e) => setDivision(e.target.value)}>
                  <option>J&amp;J Innovative Medicine</option>
                  <option>J&amp;J MedTech</option>
                </select>
              </div>
              {mode !== "url" && mode !== "expand" && (
                <div>
                  <label className="label-xs">Franchise (optional)</label>
                  <input className="input mt-1" value={franchise} onChange={(e) => setFranchise(e.target.value)} placeholder="e.g. Oncology" />
                </div>
              )}
            </div>
          )}
        </div>

        <div className="mt-5 flex justify-end gap-2">
          <button className="btn-ghost" onClick={onClose}>
            Close
          </button>
          <button className="btn-primary" disabled={!canSubmit} onClick={submit}>
            {busy && <Loader2 size={15} className="animate-spin" />} {busy ? "Ingesting…" : "Run Ingestion"}
          </button>
        </div>

        {error && <div className="mt-4 rounded-lg border border-red-900 bg-red-950/40 px-3 py-2 text-sm text-red-300">{error}</div>}

        {result && (
          <div className={`mt-4 rounded-lg border p-3 ${statusColor}`}>
            <div className="flex items-center gap-2 text-sm font-semibold">
              {result.status === "rejected" ? <AlertOctagon size={15} /> : <CheckCircle2 size={15} />}
              Status: {result.status} · +{result.added_nodes.length} nodes · +{result.added_edges.length} edges · graph now {result.node_count} nodes / {result.edge_count} edges
            </div>
            {result.rejected_kenvue_brands.length > 0 && (
              <div className="mt-2 text-xs">
                Rejected Kenvue consumer brands:{" "}
                {result.rejected_kenvue_brands.map((b) => (
                  <span key={b} className="pill mr-1 border-red-800 bg-red-950/60 text-red-200">
                    {b}
                  </span>
                ))}
              </div>
            )}
            {result.messages.length > 0 && (
              <ul className="mt-2 max-h-36 list-disc space-y-0.5 overflow-y-auto pl-4 text-xs text-slate-300">
                {result.messages.map((m, i) => (
                  <li key={i}>{m}</li>
                ))}
              </ul>
            )}
            {result.added_nodes.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
                {result.added_nodes.slice(0, 30).map((n) => (
                  <span key={n.id} className="pill border-slate-700 bg-slate-900 text-[10px] text-slate-300" title={n.id}>
                    {n.label}: {n.name}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
