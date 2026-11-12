import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  ExternalLink,
  FileText,
  Filter,
  Loader2,
  Maximize2,
  RefreshCw,
  Search,
  ShieldCheck,
  X,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { api } from "../api/client";
import {
  ALL_NODE_LABELS,
  DEFAULT_NODE_LABELS,
  DIVISIONS,
  NODE_COLORS,
  type Division,
  type EgoPayload,
  type GraphLinkData,
  type GraphNodeData,
  type GraphPayload,
  type NodeLabel,
} from "../types/graph";

/* ------------------------------------------------------------------------------------------------
 * ForceGraphCanvas — dependency-free HTML5 canvas force-directed renderer
 * ---------------------------------------------------------------------------------------------- */

interface SimNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
  fixed: boolean;
}

interface ForceGraphCanvasProps {
  nodes: GraphNodeData[];
  links: GraphLinkData[];
  selectedId?: string | null;
  highlight?: Map<string, number> | null;
  onSelect?: (id: string | null) => void;
  className?: string;
  showLegend?: boolean;
}

const RADIUS: Partial<Record<NodeLabel, number>> = {
  BusinessUnit: 13,
  Franchise: 10,
  Procedure: 12,
  Product: 8,
  SoftwareModule: 7.5,
  EvidenceDocument: 6.5,
  BoxedWarning: 6.5,
};

const nodeRadius = (n: GraphNodeData) => (RADIUS[n.label] ?? 6) + Math.min(4, (n.degree ?? 0) * 0.25);
const nodeColor = (n: GraphNodeData) => n.color ?? NODE_COLORS[n.label] ?? "#CBD5E1";
const truncate = (s: string, n: number) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);

export function ForceGraphCanvas({ nodes, links, selectedId, highlight, onSelect, className, showLegend = true }: ForceGraphCanvasProps) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const simRef = useRef<Map<string, SimNode>>(new Map());
  const alphaRef = useRef(1);
  const viewRef = useRef({ k: 1, x: 0, y: 0 });
  const sizeRef = useRef({ w: 800, h: 600 });
  const hoverRef = useRef<string | null>(null);
  const dragRef = useRef<{ mode: "node" | "pan" | null; id?: string; sx: number; sy: number; moved: boolean; vx: number; vy: number }>({
    mode: null,
    sx: 0,
    sy: 0,
    moved: false,
    vx: 0,
    vy: 0,
  });
  const propsRef = useRef({ nodes, links, selectedId, highlight });
  propsRef.current = { nodes, links, selectedId, highlight };
  // 0 = needs fit, 1 = fitted mid-layout, 2 = fitted after cooling (or user took control of the view).
  const fittedRef = useRef(0);

  // Sync simulation nodes with props while preserving existing positions.
  useEffect(() => {
    const sim = simRef.current;
    const ids = new Set(nodes.map((n) => n.id));
    let removed = 0;
    for (const id of Array.from(sim.keys()))
      if (!ids.has(id)) {
        sim.delete(id);
        removed++;
      }
    const anchor = new Map<string, SimNode>();
    links.forEach((l) => {
      const s = sim.get(l.source);
      const t = sim.get(l.target);
      if (s && !sim.has(l.target)) anchor.set(l.target, s);
      if (t && !sim.has(l.source)) anchor.set(l.source, t);
    });
    let added = 0;
    nodes.forEach((n, i) => {
      if (sim.has(n.id)) return;
      const a = anchor.get(n.id);
      const angle = (i / Math.max(1, nodes.length)) * Math.PI * 2;
      const r = a ? 30 + Math.random() * 30 : 120 + Math.random() * 220;
      sim.set(n.id, {
        x: (a?.x ?? 0) + Math.cos(angle) * r,
        y: (a?.y ?? 0) + Math.sin(angle) * r,
        vx: 0,
        vy: 0,
        fixed: false,
      });
      added++;
    });
    if (added > 0 || removed > 0) {
      alphaRef.current = Math.max(alphaRef.current, added > nodes.length / 2 ? 1 : 0.5);
      if (removed > 0 || added > nodes.length / 2) fittedRef.current = 0;
    }
  }, [nodes, links]);

  const fitToView = useCallback(() => {
    const sim = simRef.current;
    if (!sim.size) return;
    let minX = Infinity,
      minY = Infinity,
      maxX = -Infinity,
      maxY = -Infinity;
    sim.forEach((p) => {
      minX = Math.min(minX, p.x);
      minY = Math.min(minY, p.y);
      maxX = Math.max(maxX, p.x);
      maxY = Math.max(maxY, p.y);
    });
    const { w, h } = sizeRef.current;
    const k = Math.min(2.2, Math.max(0.2, Math.min(w / (maxX - minX + 140), h / (maxY - minY + 140))));
    viewRef.current = { k, x: w / 2 - ((minX + maxX) / 2) * k, y: h / 2 - ((minY + maxY) / 2) * k };
  }, []);

  const zoomBy = useCallback((factor: number, cx?: number, cy?: number) => {
    const v = viewRef.current;
    const { w, h } = sizeRef.current;
    const px = cx ?? w / 2;
    const py = cy ?? h / 2;
    const k = Math.min(5, Math.max(0.15, v.k * factor));
    const wx = (px - v.x) / v.k;
    const wy = (py - v.y) / v.k;
    viewRef.current = { k, x: px - wx * k, y: py - wy * k };
    fittedRef.current = 2;
  }, []);

  // Physics + render loop.
  useEffect(() => {
    let raf = 0;
    const step = () => {
      const { nodes: ns, links: ls } = propsRef.current;
      const sim = simRef.current;
      const alpha = alphaRef.current;
      if (alpha > 0.004) {
        const arr = ns.map((n) => sim.get(n.id)).filter(Boolean) as SimNode[];
        for (let i = 0; i < arr.length; i++) {
          const a = arr[i];
          for (let j = i + 1; j < arr.length; j++) {
            const b = arr[j];
            let dx = a.x - b.x;
            let dy = a.y - b.y;
            let d2 = dx * dx + dy * dy;
            if (d2 < 0.01) {
              dx = Math.random() - 0.5;
              dy = Math.random() - 0.5;
              d2 = 0.25;
            }
            if (d2 > 250000) continue;
            const f = (2600 * alpha) / d2;
            const fx = dx * f;
            const fy = dy * f;
            a.vx += fx;
            a.vy += fy;
            b.vx -= fx;
            b.vy -= fy;
          }
        }
        for (const l of ls) {
          const s = sim.get(l.source);
          const t = sim.get(l.target);
          if (!s || !t) continue;
          const dx = t.x - s.x;
          const dy = t.y - s.y;
          const d = Math.sqrt(dx * dx + dy * dy) || 1;
          const f = ((d - 95) / d) * 0.05 * alpha;
          s.vx += dx * f;
          s.vy += dy * f;
          t.vx -= dx * f;
          t.vy -= dy * f;
        }
        for (const p of arr) {
          p.vx -= p.x * 0.01 * alpha;
          p.vy -= p.y * 0.01 * alpha;
          if (p.fixed) {
            p.vx = 0;
            p.vy = 0;
            continue;
          }
          p.vx *= 0.62;
          p.vy *= 0.62;
          p.x += Math.max(-40, Math.min(40, p.vx));
          p.y += Math.max(-40, Math.min(40, p.vy));
        }
        alphaRef.current = alpha * 0.988;
        if (fittedRef.current === 0 && alpha < 0.25) {
          fitToView();
          fittedRef.current = 1;
        } else if (fittedRef.current === 1 && alpha < 0.02) {
          fitToView();
          fittedRef.current = 2;
        }
      }
      draw();
      raf = requestAnimationFrame(step);
    };

    const draw = () => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      const { nodes: ns, links: ls, selectedId: sel, highlight: hl } = propsRef.current;
      const sim = simRef.current;
      const { w, h } = sizeRef.current;
      const dpr = window.devicePixelRatio || 1;
      const v = viewRef.current;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);
      ctx.setTransform(dpr * v.k, 0, 0, dpr * v.k, dpr * v.x, dpr * v.y);
      const byId = new Map(ns.map((n) => [n.id, n]));
      const hover = hoverRef.current;
      const lit = (id: string) => !hl || hl.has(id);

      // Edges
      for (const l of ls) {
        const s = sim.get(l.source);
        const t = sim.get(l.target);
        const tn = byId.get(l.target);
        if (!s || !t || !tn) continue;
        const active = hl ? hl.has(l.source) && hl.has(l.target) : false;
        const touchesHover = hover === l.source || hover === l.target;
        ctx.globalAlpha = hl ? (active ? 0.95 : 0.06) : touchesHover ? 0.9 : 0.42;
        ctx.strokeStyle = active || touchesHover ? "#5CCFE6" : "#5B6B89";
        ctx.lineWidth = (active ? 1.6 : 1) / Math.max(0.6, v.k);
        const dx = t.x - s.x;
        const dy = t.y - s.y;
        const d = Math.sqrt(dx * dx + dy * dy) || 1;
        const r = nodeRadius(tn) + 2;
        const ex = t.x - (dx / d) * r;
        const ey = t.y - (dy / d) * r;
        ctx.beginPath();
        ctx.moveTo(s.x, s.y);
        ctx.lineTo(ex, ey);
        ctx.stroke();
        const ah = 7 / Math.max(0.7, v.k);
        const ang = Math.atan2(dy, dx);
        ctx.fillStyle = ctx.strokeStyle;
        ctx.beginPath();
        ctx.moveTo(ex, ey);
        ctx.lineTo(ex - ah * Math.cos(ang - 0.4), ey - ah * Math.sin(ang - 0.4));
        ctx.lineTo(ex - ah * Math.cos(ang + 0.4), ey - ah * Math.sin(ang + 0.4));
        ctx.closePath();
        ctx.fill();
        if ((active && v.k > 0.55) || touchesHover || v.k > 1.6) {
          ctx.globalAlpha = hl && !active ? 0.1 : 0.9;
          ctx.font = `${9 / Math.max(0.8, v.k)}px 'Inter Variable', Inter, sans-serif`;
          ctx.fillStyle = "#A6E9F5";
          ctx.textAlign = "center";
          const mx = (s.x + ex) / 2;
          const my = (s.y + ey) / 2;
          ctx.save();
          ctx.translate(mx, my);
          ctx.rotate(Math.abs(ang) > Math.PI / 2 ? ang + Math.PI : ang);
          ctx.fillText(l.relation, 0, -3 / Math.max(0.8, v.k));
          ctx.restore();
        }
      }

      // Nodes
      for (const n of ns) {
        const p = sim.get(n.id);
        if (!p) continue;
        const r = nodeRadius(n);
        const isSel = n.id === sel;
        const on = lit(n.id);
        ctx.globalAlpha = on ? 1 : 0.13;
        if (isSel || n.is_focus) {
          ctx.beginPath();
          ctx.arc(p.x, p.y, r + 6, 0, Math.PI * 2);
          ctx.fillStyle = isSel ? "rgba(225,37,27,0.38)" : "rgba(92,207,230,0.22)";
          ctx.fill();
        }
        ctx.beginPath();
        ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
        ctx.fillStyle = nodeColor(n);
        ctx.fill();
        ctx.lineWidth = (isSel ? 2.5 : 1.2) / Math.max(0.6, v.k);
        ctx.strokeStyle = isSel ? "#FFFFFF" : "#080B13";
        ctx.stroke();
        if (n.label === "BoxedWarning") {
          ctx.fillStyle = "#080B13";
          ctx.font = `bold ${r * 1.3}px sans-serif`;
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillText("!", p.x, p.y + 0.5);
          ctx.textBaseline = "alphabetic";
        }
        const showLabel = isSel || n.id === hover || (hl ? hl.has(n.id) && v.k > 0.45 : v.k > 0.95) || (n.label === "Procedure" && v.k > 0.5);
        if (showLabel && on) {
          ctx.font = `${(isSel ? 12 : 10) / Math.max(0.75, v.k)}px 'Inter Variable', Inter, sans-serif`;
          ctx.textAlign = "center";
          ctx.lineWidth = 3 / Math.max(0.75, v.k);
          ctx.strokeStyle = "rgba(8,11,19,0.92)";
          const text = truncate(n.name, isSel || n.id === hover ? 60 : 30);
          ctx.strokeText(text, p.x, p.y + r + 12 / Math.max(0.75, v.k));
          ctx.fillStyle = isSel ? "#FFFFFF" : "#E2E8F0";
          ctx.fillText(text, p.x, p.y + r + 12 / Math.max(0.75, v.k));
        }
      }
      ctx.globalAlpha = 1;
    };

    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [fitToView]);

  // Resize handling with devicePixelRatio scaling.
  useEffect(() => {
    const wrap = wrapRef.current;
    const canvas = canvasRef.current;
    if (!wrap || !canvas) return;
    const ro = new ResizeObserver(() => {
      const rect = wrap.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      const prev = sizeRef.current;
      sizeRef.current = { w: rect.width, h: rect.height };
      canvas.width = Math.max(1, Math.floor(rect.width * dpr));
      canvas.height = Math.max(1, Math.floor(rect.height * dpr));
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
      if (viewRef.current.x === 0 && viewRef.current.y === 0) {
        viewRef.current = { k: 1, x: rect.width / 2, y: rect.height / 2 };
      } else {
        viewRef.current.x += (rect.width - prev.w) / 2;
        viewRef.current.y += (rect.height - prev.h) / 2;
      }
    });
    ro.observe(wrap);
    return () => ro.disconnect();
  }, []);

  // Wheel zoom (non-passive so the page does not scroll).
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const rect = canvas.getBoundingClientRect();
      zoomBy(e.deltaY < 0 ? 1.12 : 1 / 1.12, e.clientX - rect.left, e.clientY - rect.top);
    };
    canvas.addEventListener("wheel", onWheel, { passive: false });
    return () => canvas.removeEventListener("wheel", onWheel);
  }, [zoomBy]);

  const pick = (sx: number, sy: number): string | null => {
    const v = viewRef.current;
    const wx = (sx - v.x) / v.k;
    const wy = (sy - v.y) / v.k;
    let best: string | null = null;
    let bestD = Infinity;
    for (const n of propsRef.current.nodes) {
      const p = simRef.current.get(n.id);
      if (!p) continue;
      const d = Math.hypot(p.x - wx, p.y - wy);
      const r = nodeRadius(n) + 4 / v.k;
      if (d <= r && d < bestD) {
        best = n.id;
        bestD = d;
      }
    }
    return best;
  };

  const local = (e: React.PointerEvent) => {
    const rect = canvasRef.current!.getBoundingClientRect();
    return { sx: e.clientX - rect.left, sy: e.clientY - rect.top };
  };

  const onPointerDown = (e: React.PointerEvent) => {
    const { sx, sy } = local(e);
    const id = pick(sx, sy);
    canvasRef.current?.setPointerCapture(e.pointerId);
    dragRef.current = { mode: id ? "node" : "pan", id: id ?? undefined, sx, sy, moved: false, vx: viewRef.current.x, vy: viewRef.current.y };
    if (id) {
      const p = simRef.current.get(id);
      if (p) p.fixed = true;
    }
  };

  const onPointerMove = (e: React.PointerEvent) => {
    const { sx, sy } = local(e);
    const drag = dragRef.current;
    if (!drag.mode) {
      const id = pick(sx, sy);
      hoverRef.current = id;
      if (canvasRef.current) canvasRef.current.style.cursor = id ? "pointer" : "grab";
      return;
    }
    if (Math.hypot(sx - drag.sx, sy - drag.sy) > 3) drag.moved = true;
    if (drag.mode === "pan") {
      viewRef.current.x = drag.vx + (sx - drag.sx);
      viewRef.current.y = drag.vy + (sy - drag.sy);
      fittedRef.current = 2;
      if (canvasRef.current) canvasRef.current.style.cursor = "grabbing";
    } else if (drag.id) {
      const p = simRef.current.get(drag.id);
      const v = viewRef.current;
      if (p) {
        p.x = (sx - v.x) / v.k;
        p.y = (sy - v.y) / v.k;
        alphaRef.current = Math.max(alphaRef.current, 0.25);
      }
    }
  };

  const onPointerUp = (e: React.PointerEvent) => {
    const drag = dragRef.current;
    canvasRef.current?.releasePointerCapture(e.pointerId);
    if (drag.mode === "node" && drag.id) {
      const p = simRef.current.get(drag.id);
      if (p) p.fixed = drag.moved;
      if (!drag.moved) onSelect?.(drag.id);
    } else if (drag.mode === "pan" && !drag.moved) {
      onSelect?.(null);
    }
    dragRef.current = { mode: null, sx: 0, sy: 0, moved: false, vx: 0, vy: 0 };
  };

  const legendLabels = useMemo(() => Array.from(new Set(nodes.map((n) => n.label))), [nodes]);

  return (
    <div ref={wrapRef} className={`relative h-full w-full overflow-hidden ${className ?? ""}`}>
      <canvas
        ref={canvasRef}
        className="block touch-none select-none"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerLeave={() => (hoverRef.current = null)}
        onDoubleClick={(e) => {
          const rect = canvasRef.current!.getBoundingClientRect();
          zoomBy(1.6, e.clientX - rect.left, e.clientY - rect.top);
        }}
      />
      <div className="absolute right-3 top-3 flex flex-col gap-1.5">
        <button className="btn-ghost !p-1.5" title="Zoom in" onClick={() => zoomBy(1.25)}>
          <ZoomIn size={15} />
        </button>
        <button className="btn-ghost !p-1.5" title="Zoom out" onClick={() => zoomBy(0.8)}>
          <ZoomOut size={15} />
        </button>
        <button className="btn-ghost !p-1.5" title="Fit graph" onClick={fitToView}>
          <Maximize2 size={15} />
        </button>
        <button
          className="btn-ghost !p-1.5"
          title="Re-run layout"
          onClick={() => {
            simRef.current.forEach((p) => (p.fixed = false));
            alphaRef.current = 1;
            fittedRef.current = 0;
          }}
        >
          <RefreshCw size={15} />
        </button>
      </div>
      {showLegend && (
        <div className="pointer-events-none absolute bottom-3 left-3 flex max-w-[85%] flex-wrap gap-x-3 gap-y-1 rounded-lg bg-slate-950/70 px-3 py-2">
          {legendLabels.map((l) => (
            <span key={l} className="flex items-center gap-1.5 text-[10px] text-slate-400">
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: NODE_COLORS[l] }} />
              {l}
            </span>
          ))}
        </div>
      )}
      {nodes.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center text-sm text-slate-500">No nodes match the current filters.</div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------------------------------------
 * Graph Explorer tab
 * ---------------------------------------------------------------------------------------------- */

const fmtUsd = (v: unknown) => (typeof v === "number" ? `$${v.toLocaleString("en-US")}` : null);

function PropRow({ label, value }: { label: string; value?: React.ReactNode }) {
  if (value === undefined || value === null || value === "") return null;
  return (
    <div className="py-1.5">
      <div className="label-xs">{label}</div>
      <div className="mt-0.5 text-sm text-slate-200">{value}</div>
    </div>
  );
}

export default function GraphExplorer({ refreshKey }: { refreshKey: number }) {
  const [division, setDivision] = useState<Division>("All");
  const [types, setTypes] = useState<Set<NodeLabel>>(new Set(DEFAULT_NODE_LABELS));
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [data, setData] = useState<GraphPayload>({ nodes: [], links: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [ego, setEgo] = useState<EgoPayload | null>(null);
  const [egoLoading, setEgoLoading] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setSearch(searchInput.trim()), 250);
    return () => clearTimeout(t);
  }, [searchInput]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .graph({ division, nodeTypes: Array.from(types), search })
      .then((g) => {
        if (!cancelled) {
          setData(g);
          setError(null);
        }
      })
      .catch((e: Error) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [division, types, search, refreshKey]);

  const select = useCallback((id: string | null) => {
    setSelectedId(id);
    if (!id) {
      setEgo(null);
      return;
    }
    setEgoLoading(true);
    api
      .ego(id, 2)
      .then(setEgo)
      .catch((e: Error) => setError(e.message))
      .finally(() => setEgoLoading(false));
  }, []);

  // Merge the selected node's 2-hop neighbourhood into the canvas so spotlighting always shows full context.
  const display = useMemo<GraphPayload>(() => {
    if (!ego) return data;
    const nodes = new Map(data.nodes.map((n) => [n.id, n]));
    ego.nodes.forEach((n) => !nodes.has(n.id) && nodes.set(n.id, n));
    const key = (l: GraphLinkData) => `${l.source}|${l.relation}|${l.target}`;
    const links = new Map(data.links.map((l) => [key(l), l]));
    ego.links.forEach((l) => links.set(key(l), l));
    return { nodes: Array.from(nodes.values()), links: Array.from(links.values()).filter((l) => nodes.has(l.source) && nodes.has(l.target)) };
  }, [data, ego]);

  const highlight = useMemo(() => (ego ? new Map(ego.nodes.map((n) => [n.id, n.hop ?? 0])) : null), [ego]);
  const egoById = useMemo(() => new Map((ego?.nodes ?? []).map((n) => [n.id, n])), [ego]);

  const toggleType = (t: NodeLabel) =>
    setTypes((prev) => {
      const next = new Set(prev);
      if (next.has(t)) next.delete(t);
      else next.add(t);
      return next;
    });

  const center = ego?.center;
  const p = (center?.properties ?? {}) as Record<string, unknown>;
  const str = (k: string) => (typeof p[k] === "string" ? (p[k] as string) : undefined);

  return (
    <div className="grid h-[calc(100vh-110px)] min-h-[620px] grid-cols-[250px_1fr_auto] gap-4">
      {/* Left sidebar */}
      <aside className="panel flex flex-col gap-4 overflow-y-auto p-4">
        <div>
          <div className="label-xs mb-2 flex items-center gap-1.5">
            <Search size={12} /> Instant Search
          </div>
          <div className="relative">
            <input className="input pr-8" placeholder="CARTO, IL-23, esophagus…" value={searchInput} onChange={(e) => setSearchInput(e.target.value)} />
            {searchInput && (
              <button className="absolute right-2 top-2.5 text-slate-500 hover:text-white" onClick={() => setSearchInput("")}>
                <X size={14} />
              </button>
            )}
          </div>
        </div>
        <div>
          <div className="label-xs mb-2">Division</div>
          <div className="flex flex-wrap gap-1.5">
            {DIVISIONS.map((d) => (
              <button
                key={d}
                onClick={() => setDivision(d)}
                className={`pill ${division === d ? "border-jnj/50 bg-jnj/15 text-white" : "border-white/[0.08] text-slate-400 hover:border-white/20 hover:text-slate-200"}`}
              >
                {d}
              </button>
            ))}
          </div>
        </div>
        <div>
          <div className="label-xs mb-2 flex items-center gap-1.5">
            <Filter size={12} /> Node Types
          </div>
          <div className="space-y-1">
            {ALL_NODE_LABELS.map((t) => (
              <label key={t} className="flex cursor-pointer items-center gap-2 rounded-lg px-1.5 py-1 text-[13px] text-slate-300 transition hover:bg-white/[0.04]">
                <input type="checkbox" className="accent-cyan-400" checked={types.has(t)} onChange={() => toggleType(t)} />
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: NODE_COLORS[t] }} />
                {t}
              </label>
            ))}
          </div>
        </div>
        <div className="mt-auto rounded-xl border border-white/[0.06] bg-slate-950/40 p-3 text-xs text-slate-400">
          <div className="flex items-center justify-between">
            <span>Visible nodes</span>
            <span className="font-mono text-clinical">{display.nodes.length}</span>
          </div>
          <div className="mt-1 flex items-center justify-between">
            <span>Visible edges</span>
            <span className="font-mono text-clinical">{display.links.length}</span>
          </div>
          <p className="mt-2 leading-relaxed text-slate-500">Scroll to zoom · drag canvas to pan · drag nodes · click a node to spotlight its 2-hop neighbourhood.</p>
        </div>
      </aside>

      {/* Canvas */}
      <section className="panel relative overflow-hidden bg-[radial-gradient(ellipse_at_center,rgba(92,207,230,0.06),transparent_70%)]">
        {loading && (
          <div className="absolute left-3 top-3 z-10 flex items-center gap-2 rounded-lg border border-white/[0.08] bg-slate-900/80 px-2.5 py-1 backdrop-blur text-xs text-slate-400">
            <Loader2 size={12} className="animate-spin" /> Loading graph…
          </div>
        )}
        {error && <div className="absolute left-3 top-3 z-10 rounded-md bg-red-950/80 px-3 py-1.5 text-xs text-red-300">{error}</div>}
        {ego && (
          <div className="absolute left-3 top-3 z-10 rounded-lg border border-white/[0.08] bg-slate-900/80 px-3 py-1.5 backdrop-blur text-xs text-slate-300">
            Spotlight: <span className="font-semibold text-white">{ego.center.name}</span> · {ego.one_hop.length} one-hop · {ego.two_hop.length} two-hop
          </div>
        )}
        <ForceGraphCanvas nodes={display.nodes} links={display.links} selectedId={selectedId} highlight={highlight} onSelect={select} />
      </section>

      {/* Inspector drawer */}
      <aside className={`panel overflow-y-auto transition-all duration-300 ${selectedId ? "w-[360px] p-4" : "w-0 border-0 p-0"}`}>
        {selectedId && (
          <div>
            <div className="mb-3 flex items-start justify-between gap-2">
              <div>
                <span className="pill border-slate-700 text-[10px]" style={{ color: center ? NODE_COLORS[center.label] : undefined }}>
                  {center?.label ?? "…"}
                </span>
                <h3 className="display mt-2 text-2xl leading-tight">{center?.name ?? selectedId}</h3>
                <div className="font-mono text-[11px] text-slate-500">{selectedId}</div>
              </div>
              <button className="text-slate-500 hover:text-white" onClick={() => select(null)}>
                <X size={18} />
              </button>
            </div>
            {egoLoading && !ego && (
              <div className="flex items-center gap-2 text-sm text-slate-400">
                <Loader2 size={14} className="animate-spin" /> Traversing 2-hop neighbourhood…
              </div>
            )}
            {ego && center && (
              <div className="divide-y divide-slate-800">
                <div className="pb-2">
                  <PropRow label="SKU" value={str("sku") && <span className="font-mono text-clinical">{str("sku")}</span>} />
                  <PropRow label="Division" value={center.division} />
                  <PropRow label="Franchise" value={center.franchise} />
                  <PropRow
                    label="Price Estimate"
                    value={fmtUsd(p.price_usd) && `${fmtUsd(p.price_usd)} ${p.pricing_model === "capital" ? "(capital)" : "/ procedure"}`}
                  />
                  <PropRow label="Category" value={str("category")} />
                  <PropRow label="Generic Name" value={str("generic_name")} />
                  <PropRow label="Mechanism of Action" value={str("mechanism")} />
                  <PropRow label="Indication" value={str("indication")} />
                  <PropRow label="Clinical Claim" value={str("clinical_claim") && <span className="italic">“{str("clinical_claim")}”</span>} />
                  <PropRow label="Trial Data" value={str("trial_data")} />
                  <PropRow label="Modality" value={str("modality")} />
                  <PropRow label="Evidence Excerpt" value={str("excerpt")} />
                </div>
                {(str("boxed_warning") || str("warning_text") || ego.lineage.boxed_warnings.length > 0) && (
                  <div className="my-2 rounded-lg border border-red-900 bg-red-950/40 p-3">
                    <div className="mb-1 flex items-center gap-1.5 text-xs font-bold uppercase text-red-400">
                      <AlertTriangle size={13} /> Boxed Warning
                    </div>
                    <div className="text-sm text-red-200">
                      {str("boxed_warning") ?? str("warning_text") ?? (ego.lineage.boxed_warnings[0]?.properties?.warning_text as string)}
                    </div>
                  </div>
                )}
                {(str("contraindication") || ego.lineage.contraindications.length > 0) && (
                  <div className="py-2">
                    <div className="label-xs mb-1">Contraindications</div>
                    <ul className="list-disc space-y-0.5 pl-4 text-sm text-amber-200">
                      {ego.lineage.contraindications.length
                        ? ego.lineage.contraindications.map((c) => (
                            <li key={c.id}>
                              {c.name} {c.severity && <span className="text-xs text-amber-400">({c.severity})</span>}
                            </li>
                          ))
                        : [<li key="c">{str("contraindication")}</li>]}
                    </ul>
                  </div>
                )}
                {ego.lineage.evidence_documents.length > 0 && (
                  <div className="py-2">
                    <div className="label-xs mb-1 flex items-center gap-1">
                      <ShieldCheck size={12} className="text-emerald-400" /> Evidence Provenance
                    </div>
                    {ego.lineage.evidence_documents.map((d) => (
                      <button key={d.id} onClick={() => select(d.id)} className="mb-1 flex w-full items-start gap-1.5 text-left text-xs text-slate-300 hover:text-clinical">
                        <FileText size={12} className="mt-0.5 shrink-0" /> {d.name}
                      </button>
                    ))}
                  </div>
                )}
                {str("source_url") && (
                  <div className="py-2">
                    <a href={str("source_url")} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-xs text-clinical hover:underline">
                      <ExternalLink size={12} /> {truncate(str("source_url")!, 48)}
                    </a>
                  </div>
                )}
                {[
                  { title: "1-Hop Neighbours", ids: ego.one_hop },
                  { title: "2-Hop Neighbours", ids: ego.two_hop },
                ].map(({ title, ids }) => (
                  <div key={title} className="py-2">
                    <div className="label-xs mb-1.5">
                      {title} ({ids.length})
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {ids.map((id) => {
                        const n = egoById.get(id);
                        if (!n) return null;
                        return (
                          <button
                            key={id}
                            onClick={() => select(id)}
                            className="pill border-slate-700 bg-slate-800/50 text-slate-300 hover:border-clinical hover:text-white"
                            title={n.label}
                          >
                            <span className="h-2 w-2 rounded-full" style={{ background: NODE_COLORS[n.label] }} />
                            {truncate(n.name, 30)}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))}
                {ego.paths.length > 0 && (
                  <details className="py-2">
                    <summary className="label-xs cursor-pointer">Serialized graph paths ({ego.paths.length})</summary>
                    <ul className="mt-1 space-y-1">
                      {ego.paths.slice(0, 40).map((path) => (
                        <li key={path} className="font-mono text-[10px] leading-snug text-slate-400">
                          {path}
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
              </div>
            )}
          </div>
        )}
      </aside>
    </div>
  );
}
