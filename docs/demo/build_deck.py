"""Build the POC demo deck (docs/JnJ-GraphRAG-Nexus-Demo.pptx) from PITCH.md content + live app screenshots.

Usage:  python docs/demo/build_deck.py      (screenshots: python docs/demo/capture_screenshots.py docs/demo)
"""
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "JnJ-GraphRAG-Nexus-Demo.pptx"

INK = RGBColor(0x0B, 0x12, 0x20)
MUTED = RGBColor(0x5B, 0x67, 0x7A)
PAGE = RGBColor(0xF4, 0xF6, 0xFA)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
ZEBRA = RGBColor(0xF8, 0xFA, 0xFC)
LINE = RGBColor(0xE2, 0xE7, 0xEF)
RED = RGBColor(0xD5, 0x19, 0x00)
RED_SOFT = RGBColor(0xFD, 0xEC, 0xE9)
TEAL = RGBColor(0x0A, 0x7C, 0x93)
TEAL_SOFT = RGBColor(0xE6, 0xF4, 0xF7)
GOLD = RGBColor(0xA9, 0x77, 0x1F)
GOLD_SOFT = RGBColor(0xFB, 0xF4, 0xE6)
GREEN = RGBColor(0x0F, 0x8A, 0x5F)
GREEN_SOFT = RGBColor(0xE8, 0xF6, 0xEF)

SERIF, SANS = "Georgia", "Segoe UI"

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]
_page = {"n": 0}


def rect(s, x, y, w, h, fill, line=None, shape=MSO_SHAPE.RECTANGLE, radius=0.06):
    sh = s.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.fill.solid()
    sh.fill.fore_color.rgb = fill
    if line is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = line
        sh.line.width = Pt(0.75)
    sh.shadow.inherit = False
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        sh.adjustments[0] = radius
    return sh


def card(s, x, y, w, h, fill=WHITE, line=LINE, radius=0.06):
    return rect(s, x, y, w, h, fill, line, MSO_SHAPE.ROUNDED_RECTANGLE, radius)


def text(s, x, y, w, h, lines, size=14, color=INK, font=SANS, bold=False, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, spacing=1.1, after=0):
    """lines: str | list of (str | list of segments); segment = str | (str, {size,color,bold,italic,font})."""
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    for i, line in enumerate([lines] if isinstance(lines, str) else lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment, p.line_spacing, p.space_after = align, spacing, Pt(after)
        for seg in line if isinstance(line, list) else [line]:
            t, o = (seg, {}) if isinstance(seg, str) else seg
            r = p.add_run()
            r.text = t
            f = r.font
            f.name = o.get("font", font)
            f.size = Pt(o.get("size", size))
            f.bold = o.get("bold", bold)
            f.italic = o.get("italic", False)
            f.color.rgb = o.get("color", color)
    return tb


def bullets(s, x, y, w, h, items, size=13, color=INK, marker=RED, after=7):
    return text(s, x, y, w, h, [[("\u25A0  ", {"size": size - 5, "color": marker}), it] if isinstance(it, str)
                                else [("\u25A0  ", {"size": size - 5, "color": marker})] + it for it in items],
                size=size, color=color, after=after)


def pill(s, x, y, label, fill=TEAL_SOFT, color=TEAL, w=None, size=10.5):
    w = w or 0.22 + len(label) * 0.085
    card(s, x, y, w, 0.32, fill, None, radius=0.5)
    text(s, x, y, w, 0.32, label, size=size, color=color, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    return w


def base(title, kicker=None, notes=""):
    s = prs.slides.add_slide(BLANK)
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = PAGE
    rect(s, 0, 0, 13.333, 0.07, RED)
    if kicker:
        text(s, 0.6, 0.42, 10, 0.3, kicker.upper(), size=11, color=TEAL, bold=True)
    text(s, 0.6, 0.68, 12.1, 0.75, title, size=30, font=SERIF)
    _page["n"] += 1
    text(s, 0.6, 7.08, 8, 0.25, [[("J&J ", {"color": RED, "bold": True}), "GraphRAG Nexus  \u00B7  POC demo"]],
         size=9, color=MUTED)
    text(s, 11.73, 7.08, 1.0, 0.25, str(_page["n"]), size=9, color=MUTED, align=PP_ALIGN.RIGHT)
    if notes:
        s.notes_slide.notes_text_frame.text = notes
    return s


def shot(s, name, x, y, w):
    h = w * 9 / 16
    card(s, x - 0.05, y - 0.05, w + 0.1, h + 0.1, radius=0.02)
    s.shapes.add_picture(str(HERE / f"{name}.png"), Inches(x), Inches(y), Inches(w), Inches(h))
    return h


def table(s, x, y, rows, widths, size=11, row_h=0.4, hi_col=None, header=INK):
    shp = s.shapes.add_table(len(rows), len(rows[0]), Inches(x), Inches(y), Inches(sum(widths)), Inches(row_h * len(rows)))
    tbl = shp.table
    for j, cw in enumerate(widths):
        tbl.columns[j].width = Inches(cw)
    for i, row in enumerate(rows):
        tbl.rows[i].height = Inches(row_h)
        for j, val in enumerate(row):
            c = tbl.cell(i, j)
            c.fill.solid()
            c.fill.fore_color.rgb = header if i == 0 else (WHITE if i % 2 else ZEBRA)
            c.margin_left = c.margin_right = Inches(0.1)
            c.margin_top = c.margin_bottom = Inches(0.03)
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            p = c.text_frame.paragraphs[0]
            c.text_frame.word_wrap = True
            r = p.add_run()
            r.text = str(val)
            f = r.font
            f.name, f.size = SANS, Pt(size)
            f.color.rgb = WHITE if i == 0 else INK
            f.bold = i == 0 or j == 0
            if hi_col is not None and i > 0 and j == hi_col:
                f.color.rgb, f.bold = TEAL, True
    return tbl


def demo_slide(step, title, img, show, why, metric=None, notes=""):
    s = base(title, f"Live demo \u00B7 step {step}", notes)
    shot(s, img, 0.6, 1.6, 8.45)
    x, w = 9.35, 3.38
    text(s, x, 1.55, w, 0.3, "WHAT TO SHOW", size=10.5, color=MUTED, bold=True)
    bullets(s, x, 1.88, w, 3.0, show, size=12, after=6)
    y = 5.0
    if metric:
        card(s, x, y - 0.05, w, 0.78, WHITE)
        text(s, x + 0.18, y + 0.04, w - 0.3, 0.6, [[(metric[0], {"size": 22, "font": SERIF, "color": RED})],
                                                  [(metric[1], {"size": 10, "color": MUTED})]])
        y += 0.88
    card(s, x, y, w, 6.38 - y + 0.4, TEAL_SOFT, None)
    text(s, x + 0.18, y + 0.12, w - 0.34, 6.38 - y + 0.2, [[("WHY IT MATTERS", {"size": 10, "bold": True, "color": TEAL})], why],
         size=12, spacing=1.08, after=3)
    return s


# 1. Title ------------------------------------------------------------------------------------------
s = prs.slides.add_slide(BLANK)
s.background.fill.solid()
s.background.fill.fore_color.rgb = PAGE
rect(s, 0, 0, 0.18, 7.5, RED)
card(s, 0.75, 0.75, 0.75, 0.75, RED, None, radius=0.22)
text(s, 0.75, 0.75, 0.75, 0.75, "J&J", size=16, color=WHITE, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
text(s, 0.75, 1.95, 6.2, 0.4, "PROOF OF CONCEPT \u00B7 DEMO", size=12, color=TEAL, bold=True)
text(s, 0.75, 2.35, 6.4, 1.6, [[("GraphRAG ", {}), ("Nexus", {"italic": True, "color": GOLD})]], size=50, font=SERIF)
text(s, 0.75, 3.5, 5.9, 1.2, "One cited knowledge layer connecting J&J Innovative Medicine and MedTech products to "
     "procedures, anatomy, conditions and regulatory evidence.", size=17, color=MUTED, spacing=1.15)
px = 0.75
for lbl, f, c in [("Graph-grounded", TEAL_SOFT, TEAL), ("Every answer cited", GREEN_SOFT, GREEN),
                  ("Kenvue-safe", RED_SOFT, RED), ("$0 licence \u00B7 runs offline", GOLD_SOFT, GOLD)]:
    px += pill(s, px, 4.95, lbl, f, c) + 0.12
text(s, 0.75, 6.6, 6, 0.3, "Hours of siloed searching \u2192 seconds, with provenance.", size=12, color=MUTED, bold=True)
shot(s, "02-graph-carto-spotlight", 7.05, 1.55, 5.75)
text(s, 7.05, 4.95, 5.75, 0.3, "Knowledge Graph Explorer \u2014 CARTO 3 System V8 spotlight", size=10, color=MUTED,
     align=PP_ALIGN.CENTER)
s.notes_slide.notes_text_frame.text = (
    "Opening line: 'Where do our products meet in an AFib procedure \u2014 and can we prove every claim?' "
    "Nexus answers that in seconds today; it takes hours across siloed systems. Everything you will see runs on this laptop "
    "with open-source components and no API keys.")

# 2. Problem ----------------------------------------------------------------------------------------
s = base("Siloed knowledge costs time, revenue and compliance", "The problem \u00B7 why now",
         "Walk the five pain points left to right. Emphasise that each is owned by a different function, which is why "
         "no single team has fixed it. The common root cause: no shared, cited, connected knowledge layer.")
pains = [
    ("FIELD SALES / KAMs", "Siloed by franchise", "Reps know their own bag; cross-franchise opportunities in the same procedure are missed."),
    ("MEDICAL AFFAIRS / MSLs", "Slow evidence answers", "\u2018Which products are used in procedure X and what supports them?\u2019 = manual PI, IFU, DailyMed search."),
    ("MLR REVIEWERS", "Line-by-line label checks", "Every promotional claim is read against the PI/IFU by hand \u2014 the main content bottleneck."),
    ("COMMERCIAL OPS", "Kenvue separation", "Legacy consumer brands still leak into content, data feeds and search after 2023."),
    ("IT / AI CoE", "Plain RAG chatbots", "Hallucinations, no traceability, no multi-hop reasoning (product \u2192 procedure \u2192 anatomy \u2192 risk)."),
]
for i, (who, head, today) in enumerate(pains):
    x = 0.6 + i * 2.45
    card(s, x, 1.75, 2.3, 4.1)
    rect(s, x + 0.22, 2.0, 0.5, 0.05, RED)
    text(s, x + 0.22, 2.2, 1.95, 0.5, who, size=10, color=TEAL, bold=True)
    text(s, x + 0.22, 2.75, 1.95, 0.9, head, size=18, font=SERIF, spacing=1.0)
    text(s, x + 0.22, 3.75, 1.9, 2.0, today, size=12, color=MUTED, spacing=1.15)
card(s, 0.6, 6.1, 12.13, 0.7, INK, None)
text(s, 0.85, 6.1, 11.7, 0.7, [[("Net effect:  ", {"bold": True, "color": GOLD}),
                               ("hours per question, missed cross-sector revenue, and MLR as the throughput bottleneck.", {"color": WHITE})]],
     size=14, anchor=MSO_ANCHOR.MIDDLE)

# 3. Solution / architecture -------------------------------------------------------------------------
s = base("What Nexus does: sanctioned sources in, cited answers out", "The solution",
         "Explain left to right. Key differentiator: the graph is the source of truth and every fact keeps its provenance; "
         "the LLM is optional and only phrases the answer. Guardrails are enforced in code at ingestion AND query time.")
steps = [
    ("1  SOURCES", "jnj.com \u00B7 NIH DailyMed \u00B7 openFDA (labels, FAERS, recalls) \u00B7 ClinicalTrials.gov \u00B7 PubMed \u00B7 PDFs"),
    ("2  INGEST + GUARDRAILS", "Kenvue brand block \u00B7 PHI redaction \u00B7 prompt-injection filter \u00B7 freshness scheduling"),
    ("3  KNOWLEDGE GRAPH", "15 typed node kinds (product, procedure, anatomy, evidence, boxed warning\u2026) with provenance on every edge"),
    ("4  HYBRID RETRIEVAL", "BM25 + vector + 2-hop graph expansion, fused and cross-encoder reranked"),
    ("5  LANGGRAPH AGENTS", "Supervisor router \u2192 specialist agent \u2192 grounded synthesiser with citations"),
]
for i, (h, b) in enumerate(steps):
    x = 0.6 + i * 2.48
    card(s, x, 1.75, 2.18, 2.75, WHITE)
    rect(s, x, 1.75, 2.18, 0.08, [TEAL, GOLD, RED, TEAL, GOLD][i])
    text(s, x + 0.18, 2.0, 1.85, 0.4, h, size=10.5, color=TEAL, bold=True)
    text(s, x + 0.18, 2.45, 1.85, 2.0, b, size=12, spacing=1.15)
    if i < 4:
        a = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x + 2.22), Inches(2.95), Inches(0.22), Inches(0.3))
        a.fill.solid()
        a.fill.fore_color.rgb = MUTED
        a.line.fill.background()
text(s, 0.6, 4.85, 12, 0.3, "FIVE WORKSPACES ON TOP OF ONE GRAPH", size=10.5, color=MUTED, bold=True)
apps = [("Knowledge Graph", "Explore & spotlight"), ("Cross-Sell Bundler", "Procedure economics"),
        ("Agent Co-Pilot", "Cited Q&A"), ("MLR Pre-Review", "Claim compliance"), ("Sources & Ops", "Freshness, audit, evals")]
for i, (a, d) in enumerate(apps):
    x = 0.6 + i * 2.48
    card(s, x, 5.2, 2.3, 0.95, INK, None)
    text(s, x + 0.18, 5.3, 2.0, 0.8, [[(a, {"bold": True, "color": WHITE, "size": 13})], [(d, {"color": RGBColor(0xB8, 0xC2, 0xD3), "size": 11})]],
         anchor=MSO_ANCHOR.MIDDLE)
text(s, 0.6, 6.4, 12.1, 0.5, "Also exposed as an MCP server so other AI assistants can query the same governed graph.  "
     "Storage: NetworkX locally, mirrors to Neo4j.  LLM router: Azure OpenAI \u2192 OpenAI \u2192 Gemini \u2192 deterministic local.",
     size=11, color=MUTED)

# 4. At a glance --------------------------------------------------------------------------------------
s = base("The POC at a glance", "Working software, not slides",
         "These are real numbers from the running app and the automated evaluation, not projections. Point out the eval: "
         "GraphRAG beats keyword, dense and hybrid retrieval on the same 40-question golden set, with the biggest gain in MRR "
         "(the right answer is ranked first far more often).")
tiles = [
    ("136 / 174", "graph nodes / typed edges", TEAL), ("34", "J&J SKUs across 10 franchises", TEAL),
    ("8", "live evidence connectors", TEAL), ("$0", "licence cost \u00B7 runs fully offline", GOLD),
    ("0.975", "GraphRAG recall@5 (BM25: 0.938)", RED), ("+39%", "MRR vs keyword search (0.958 vs 0.689)", RED),
    ("1.000", "answer groundedness, 40-query golden set", RED), ("57", "automated backend tests passing", GOLD),
]
for i, (big, small, c) in enumerate(tiles):
    x, y = 0.6 + (i % 4) * 3.07, 1.75 + (i // 4) * 2.4
    card(s, x, y, 2.85, 2.1)
    rect(s, x + 0.25, y + 0.3, 0.45, 0.05, c)
    text(s, x + 0.25, y + 0.5, 2.5, 0.9, big, size=40, font=SERIF, color=INK)
    text(s, x + 0.25, y + 1.38, 2.4, 0.6, small, size=12, color=MUTED, spacing=1.1)
text(s, 0.6, 6.6, 12.1, 0.35, "Evaluation: 40-query golden set, k=5, run from the Sources & Ops workspace. Routing accuracy 0.975; "
     "co-pilot median latency \u2248 0.4 s on a laptop.", size=11, color=MUTED)

# 5. Demo agenda -------------------------------------------------------------------------------------
s = base("5-minute demo flow", "Live demo",
         "Keep strictly to time. If anything fails live, the next slides contain screenshots of each step taken from the running app.")
flow = [("0:30", "The problem", "Where do our products meet in an AFib procedure \u2014 and can we prove every claim?"),
        ("1:00", "Graph Explorer", "Search CARTO \u2192 spotlight the cross-franchise neighbourhood + evidence"),
        ("1:30", "Cross-Sell Bundler", "AFib @ 500/yr \u2192 4-tier bill of materials \u2192 deal value and uplift"),
        ("1:30", "Agent Co-Pilot + MLR", "Regulatory Auditor preset \u2192 cited claim audit \u2192 pre-review of a risky draft"),
        ("0:30", "Guardrails", "Ingest \u2018Tylenol\u2019 \u2192 rejected (Kenvue). Live sources stay fresh"),
        ("0:30", "The ask", "Pilot scope, KPIs and timeline")]
for i, (t, h, d) in enumerate(flow):
    y = 1.7 + i * 0.84
    card(s, 0.6, y, 12.13, 0.7)
    card(s, 0.75, y + 0.14, 0.95, 0.42, RED if i in (0, 5) else TEAL, None, radius=0.5)
    text(s, 0.75, y + 0.14, 0.95, 0.42, t, size=12, color=WHITE, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 1.95, y, 3.0, 0.7, h, size=16, font=SERIF, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 5.0, y, 7.5, 0.7, d, size=13, color=MUTED, anchor=MSO_ANCHOR.MIDDLE)

# 6-12. Demo steps -----------------------------------------------------------------------------------
demo_slide(1, "Graph Explorer: one connected view of the portfolio", "02-graph-carto-spotlight",
           ["Type \u201cCARTO\u201d in Instant Search \u2014 8 matching nodes", "Click CARTO 3 System V8 \u2192 spotlight: 10 one-hop, 5 two-hop neighbours",
            "Inspector: SKU, franchise, price, clinical claim", "Evidence provenance with the source IFU and URL"],
           ["Platform, software modules, catheters, anatomy and evidence across franchises \u2014 in one view, with the source of every fact."],
           notes="Search CARTO. Click the CARTO 3 System V8 node. Point at the spotlight banner (10 one-hop, 5 two-hop) and the "
                 "inspector on the right: SKU, price estimate, clinical claim and the evidence provenance link to the IFU. "
                 "Message: one connected view, every fact traceable.")
demo_slide(2, "Cross-Sell Bundler: from a capital sale to a full procedure", "03-bundler",
           ["Procedure: Catheter Ablation for AFib", "Volume slider: 500 procedures / year", "4 tiers: capital \u00B7 software \u00B7 catheters & sheaths \u00B7 Ethicon post-op",
            "Export the value-analysis proposal (.docx)"],
           ["Makes cross-franchise attach visible per account and turns one capital sale into a whole-procedure value proposition."],
           metric=("$451k \u2192 $2.80M", "Year-1 deal value \u00B7 +520% pull-through over capital (illustrative list prices)"),
           notes="Select AFib ablation, keep 500/yr, then drag the slider to show the numbers recompute deterministically from the graph. "
                 "Baseline capital $451,000; annual cross-sell pull-through $2,347,500; total year-1 deal value $2,798,500. "
                 "Every line item carries its evidence document. Prices are illustrative until we connect SAP list prices.")
demo_slide(3, "Agent Co-Pilot: multi-agent answers with ranked evidence", "04-copilot",
           ["Click the \u201cRegulatory Auditor\u201d preset", "Supervisor routes to the Regulatory Auditor agent (~0.4 s)",
            "Pipeline: hybrid search \u2192 2-hop graph expansion \u2192 reranker \u2192 domain agent", "Right rail: reranked evidence with scores and hop distance"],
           ["Answers are grounded only in retrieved graph facts. The LLM is optional \u2014 it phrases, it is not the source of truth."],
           notes="Run the Regulatory Auditor preset. Walk the LangGraph execution pipeline cards. Show the cross-encoder reranked evidence "
                 "on the right \u2014 passages and explicit graph paths with scores. Emphasise: no ungrounded free text.")
demo_slide(3, "Claim provenance audit: every claim traced to a label of record", "04b-copilot-claims",
           ["Claim table: product, claim type, claim, evidence source, status", "Indications, mechanisms, boxed warnings and trial data \u2014 verified",
            "Risk level, confidence and \u201crequires medical review\u201d flags", "\U0001F44D / \U0001F44E feedback feeds the quality dashboard"],
           ["Gives MLR and Medical a pre-checked, cited table instead of free text \u2014 audit-ready by design."],
           notes="Scroll to the Regulatory Claim Provenance Audit. Each row ties a claim to the FDA label or trial readout it came from. "
                 "Show the risk and confidence badges and the human-review flag \u2014 humans stay in the loop.")
demo_slide(4, "MLR Pre-Review: catch problems before the human review", "05b-mlr-findings",
           ["Load the \u201cNon-compliant draft\u201d sample and run pre-review", "Verdict NOT READY \u00B7 risk 99 \u00B7 3 critical, 3 warning",
            "Flags absolute language, off-label indication, unsupported superlatives", "Suggested compliant rewrites; Accept / Needs revision / Dismiss; export DOCX"],
           ["Reviewers start from a pre-screened package, cutting review cycles and stopping off-label claims early."],
           notes="Use the non-compliant TREMFYA draft: 'cures psoriasis with no side effects', 'superior to every biologic', "
                 "'effective for multiple myeloma'. Show the annotated asset, the findings with regulatory precedents and suggested rewrites, "
                 "and the reviewer decisions that are written to the audit log.")
demo_slide(5, "Guardrails: the portfolio boundary is enforced in code", "07-kenvue-guardrail",
           ["Open \u201cSync live J&J / FDA data\u201d", "FDA DailyMed \u2192 enter \u201cTylenol\u201d \u2192 Run Ingestion",
            "Rejected: Kenvue consumer-health brand, +0 nodes", "Same modal: jnj.com crawl, product URL, custom text, label PDF, evidence APIs"],
           ["Post-separation brand boundary is automatic \u2014 no reliance on prompts or reviewer memory."],
           notes="Type Tylenol and run ingestion: it is rejected before anything touches the graph. Then (optional) sync CARVYKTI from "
                 "DailyMed to show a fresh label landing in the graph as evidence.")

s = base("Sources & Ops: proof of quality, freshness and governance", "Live demo \u00B7 step 6",
         "Managers approve numbers, not demos. Show source freshness, the tamper-evident audit chain, versioned prompts and LLM cost metering. "
         "Then click Run eval: GraphRAG wins on recall and especially MRR versus BM25, dense and hybrid baselines.")
shot(s, "06-ops", 0.6, 1.6, 8.45)
text(s, 9.35, 1.55, 3.4, 0.3, "GOLDEN-SET EVALUATION (n=40, k=5)", size=10.5, color=MUTED, bold=True)
table(s, 9.35, 1.9, [["Method", "Recall@5", "MRR"], ["BM25", "0.938", "0.689"], ["Dense", "0.925", "0.539"],
                     ["Hybrid", "0.938", "0.645"], ["GraphRAG", "0.975", "0.958"]], [1.3, 1.04, 1.04], size=11, row_h=0.38)
tbl_note = [["Routing accuracy ", ("0.975", {"bold": True, "color": TEAL})], ["Groundedness ", ("1.000", {"bold": True, "color": TEAL})],
            ["Audit chain ", ("intact", {"bold": True, "color": GREEN})], ["Evidence connectors ", ("8, freshness-tracked", {"bold": True})]]
text(s, 9.35, 4.0, 3.4, 1.3, tbl_note, size=12, after=4)
card(s, 9.35, 5.45, 3.38, 1.33, TEAL_SOFT, None)
text(s, 9.53, 5.57, 3.05, 1.15, [[("WHY IT MATTERS", {"size": 10, "bold": True, "color": TEAL})],
                                 "Quality is measured in CI, not asserted \u2014 the basis for pilot exit criteria."], size=12, after=3)

# 13. Collaboration ----------------------------------------------------------------------------------
s = base("Collaboration value: IM \u00D7 MedTech, and J&J \u00D7 partners", "Why this matters to J&J",
         "This is the core argument: the value comes from connections no single franchise owns. Left: internal synergy. Right: external collaborators.")
card(s, 0.6, 1.7, 5.9, 5.1)
text(s, 0.85, 1.9, 5.4, 0.4, "INSIDE J&J \u2014 CROSS-SECTOR SYNERGY", size=10.5, color=TEAL, bold=True)
bullets(s, 0.85, 2.35, 5.45, 4.4, [
    [("Procedure-centric selling. ", {"bold": True}), "One AFib node links Biosense Webster capital & software, EP catheters, ICE ultrasound and Ethicon post-op."],
    [("IM \u2194 MedTech bridges. ", {"bold": True}), "Shared condition and anatomy nodes reveal joint patient pathways for account plans and medical education."],
    [("Shared evidence layer. ", {"bold": True}), "Medical curates once; Sales, Marketing and MLR consume the same cited facts."],
    [("Reusable platform. ", {"bold": True}), "A new franchise is a data-onboarding task, not a new build."]], size=13, after=10)
text(s, 6.85, 1.75, 5.9, 0.4, "WITH EXTERNAL COLLABORATORS", size=10.5, color=TEAL, bold=True)
table(s, 6.85, 2.1, [["Collaborator", "How the graph helps"],
                     ["Hospitals / IDNs", "Procedure-level total-cost-of-care bundles for value-based contracting"],
                     ["GPOs / procurement", "Transparent bill of materials per procedure simplifies tiering"],
                     ["FDA & public data", "Label of record (DailyMed, openFDA, GUDID, ClinicalTrials.gov) behind every claim"],
                     ["Academic / KOLs", "Trial and publication nodes support evidence-gap analysis"],
                     ["Cloud / AI partners", "Swap in Azure OpenAI and a managed graph without redesign"]],
      [1.85, 4.03], size=11, row_h=0.74)

# 14. Value model ------------------------------------------------------------------------------------
s = base("Value model: productivity, growth and risk reduction", "Business case (illustrative \u2014 replace with real baselines)",
         "All figures are illustrative assumptions for discussion; every formula is in PITCH.md section 4 so finance can re-run it. "
         "Land the payback line: even 20% realisation covers a typical pilot budget in year one, before any revenue upside.")
text(s, 0.6, 1.65, 7.3, 0.3, "PRODUCTIVITY (COST AVOIDANCE)", size=10.5, color=TEAL, bold=True)
table(s, 0.6, 2.0, [["Lever", "Formula (example)", "Annual value"],
                    ["Field search & prep", "150 reps \u00D7 2 h/wk \u00D7 46 wk \u00D7 $90", "$1,242,000"],
                    ["Med info / MSL responses", "40 users \u00D7 3 h/wk \u00D7 46 wk \u00D7 $120", "$662,400"],
                    ["MLR pre-screen", "1,200 claims \u00D7 1.5 h \u00D7 $150", "$270,000"],
                    ["Subtotal (pilot scale)", "", "\u2248 $2.17M / yr"]], [2.3, 3.4, 1.6], size=11.5, row_h=0.5, hi_col=2)
card(s, 8.25, 1.7, 4.48, 2.35)
text(s, 8.48, 1.88, 4.1, 0.3, "GROWTH", size=10.5, color=GOLD, bold=True)
text(s, 8.48, 2.2, 4.1, 0.6, "$750k / yr", size=30, font=SERIF)
text(s, 8.48, 2.85, 4.05, 1.1, "per region from 3 incremental attach deals \u00D7 $250k consumable pull-through. Demo AFib account: "
     "\u2248 $2.8M year-1 deal value, 5.2\u00D7 capital-only.", size=11.5, color=MUTED, spacing=1.12)
card(s, 8.25, 4.2, 4.48, 1.55)
text(s, 8.48, 4.36, 4.1, 0.3, "RISK REDUCTION", size=10.5, color=RED, bold=True)
text(s, 8.48, 4.68, 4.05, 1.05, "Fewer off-label/outdated claims \u00B7 automatic Kenvue boundary \u00B7 full provenance for audit.",
     size=11.5, color=MUTED, spacing=1.12)
card(s, 0.6, 5.0, 7.3, 0.75, WHITE)
text(s, 0.82, 5.0, 7.0, 0.75, [[("Cost to run: ", {"bold": True}), "POC \u2248 $0 licence \u00B7 pilot = 2\u20133 FTE + low thousands $/month Azure \u00B7 scale case at pilot exit gate"]],
     size=11.5, anchor=MSO_ANCHOR.MIDDLE, color=MUTED)
card(s, 0.6, 6.0, 12.13, 0.8, INK, None)
text(s, 0.85, 6.0, 11.7, 0.8, [[("Payback:  ", {"bold": True, "color": GOLD}),
                               ("even if only 20% of the productivity estimate is realised (\u2248 $435k), a typical pilot pays for itself in year one \u2014 before any revenue upside.",
                                {"color": WHITE})]], size=14, anchor=MSO_ANCHOR.MIDDLE)

# 15. Why GraphRAG -----------------------------------------------------------------------------------
s = base("Why GraphRAG \u2014 and not just another chatbot", "Differentiation",
         "Anticipate the 'we already have a chatbot' objection. The last column is what makes this approvable by Compliance: deterministic numbers, "
         "explicit traversal, and guardrails in code.")
table(s, 0.6, 1.75, [["Capability", "Plain LLM chatbot", "Vector RAG", "GraphRAG Nexus"],
                     ["Multi-hop questions (product \u2192 procedure \u2192 anatomy \u2192 risk)", "\u2717", "Weak", "\u2713 explicit traversal"],
                     ["Citations / provenance", "\u2717", "Chunk-level", "\u2713 node, edge & document lineage"],
                     ["Deterministic numbers (bundle prices, ROI)", "\u2717 hallucinated", "\u2717", "\u2713 computed from the graph"],
                     ["Business-rule guardrails (Kenvue, label status)", "Prompt only", "Prompt only", "\u2713 enforced in code"],
                     ["Explainability for MLR & audit", "Low", "Medium", "High \u2014 retrieval path shown in UI"],
                     ["Measured retrieval quality (MRR, golden set)", "n/a", "0.539 (dense)", "0.958"]],
      [4.6, 2.2, 2.2, 3.13], size=13, row_h=0.66, hi_col=3)

# 16. POC -> pilot -----------------------------------------------------------------------------------
s = base("From POC to pilot: what is built, what comes next", "Robustness roadmap",
         "Many items from the original gap analysis are already implemented in the POC (left). P0 items are what turns this into an approvable, "
         "secure pilot; P1/P2 are for the scale decision.")
cols = [
    ("BUILT INTO THE POC TODAY", GREEN, GREEN_SOFT, [
        "40-query golden-set eval vs BM25 / dense / hybrid", "openFDA labels, FAERS, recalls, ClinicalTrials.gov, PubMed connectors with freshness",
        "Role-based views (medical / MLR / commercial / admin) + API key", "Tamper-evident audit chain; versioned prompts",
        "MLR workflow with reviewer decisions + DOCX export", "Value-analysis proposal export (.docx)",
        "Feedback loop + usage, latency and LLM cost dashboard", "PHI redaction, prompt-injection filter, MCP server"]),
    ("P0 \u00B7 PILOT-READY (2\u20134 WEEKS)", RED, RED_SOFT, [
        "Entra ID SSO, Key Vault, private endpoints", "SAP/ERP list prices + product master replace estimates",
        "FDA AccessGUDID device sync (replaces web scraping)", "SME-authored golden set (50\u2013100 Q&A) gating CI",
        "Azure OpenAI behind a private endpoint", "Label-change diff alerts \u2192 affected claims"]),
    ("P1 / P2 \u00B7 SCALE", GOLD, GOLD_SOFT, [
        "CPT / HCPCS / DRG reimbursement layer in the bundler", "CRM push (Veeva / Salesforce) for proposals",
        "Bitemporal graph versioning (\u2018label on date X\u2019)", "Azure Container Apps + managed Neo4j / Cosmos",
        "App Insights tracing, SLOs, load tests", "EU SmPC / Japan PMDA labels; SharePoint & Veeva Vault connectors"]),
]
for i, (h, c, soft, items) in enumerate(cols):
    x = 0.6 + i * 4.1
    card(s, x, 1.7, 3.93, 5.15)
    rect(s, x, 1.7, 3.93, 0.08, c)
    card(s, x + 0.22, 1.98, 3.5, 0.38, soft, None, radius=0.5)
    text(s, x + 0.22, 1.98, 3.5, 0.38, h, size=10.5, color=c, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    bullets(s, x + 0.25, 2.55, 3.5, 4.2, items, size=11.5, marker=c, after=6)

# 17. Risks ------------------------------------------------------------------------------------------
s = base("Risks and mitigations", "De-risking",
         "Show that each risk compliance or IT will raise already has a concrete mitigation, several of them already built.")
table(s, 0.6, 1.75, [["Risk", "Mitigation"],
                     ["Hallucinated or off-label output", "Grounded generation from retrieved graph facts only; claim auditor flags anything unsupported; MLR stays in the loop."],
                     ["Data accuracy (curated prices are estimates)", "Pilot replaces them with SAP/ERP list prices and MDM product masters."],
                     ["Scraping is fragile (jnjmedtech.com returns 403)", "Move to sanctioned sources: product master, GUDID for devices, DailyMed/openFDA for drugs."],
                     ["Security / compliance", "No PHI/PII used; PHI redaction built in. Add Entra ID SSO, RBAC, private endpoints, audit logging before user access."],
                     ["Adoption", "Embed in existing tools (CRM / Teams); start with 1\u20132 high-pain use cases."]],
      [3.8, 8.33], size=13, row_h=0.8)

# 18. The ask ----------------------------------------------------------------------------------------
s = base("The ask: a 10\u201312 week pilot with agreed exit criteria", "Decision requested",
         "Be explicit about the ask and agree the exit criteria up front, so the go/no-go at week 12 is objective.")
card(s, 0.6, 1.7, 5.5, 5.1)
text(s, 0.85, 1.9, 5.0, 0.3, "PILOT SCOPE", size=10.5, color=TEAL, bold=True)
bullets(s, 0.85, 2.3, 5.05, 4.4, [
    [("Scope: ", {"bold": True}), "1 procedure family (EP / AFib) + 1 IM therapeutic area (oncology), 1 region"],
    [("Users: ", {"bold": True}), "\u2248 20 reps / KAMs, 5 MSLs, 2\u20133 MLR reviewers"],
    [("Duration: ", {"bold": True}), "10\u201312 weeks"],
    [("We need: ", {"bold": True}), "read access to product master & list prices; an Azure sandbox; 2 h/week each from an MLR and a Medical Affairs SME; "
                                    "an executive sponsor in Commercial Excellence"]], size=13, after=10)
text(s, 6.45, 1.75, 6.3, 0.3, "EXIT CRITERIA (AGREE UP FRONT)", size=10.5, color=TEAL, bold=True)
table(s, 6.45, 2.1, [["KPI", "Target"], ["Answer groundedness on golden set", "\u2265 95%"], ["Citation accuracy", "\u2265 98%"],
                     ["Time to answer a procedure / evidence question", "\u221270% vs baseline"],
                     ["MLR pre-screen precision (reviewer agrees)", "\u2265 80%"], ["Weekly active pilot users", "\u2265 60%"],
                     ["Bundle proposals / attach opportunities logged", "\u2265 10"]], [4.28, 2.0], size=12, row_h=0.62, hi_col=1)

# 19. Objections -------------------------------------------------------------------------------------
s = base("Likely questions", "Objection handling",
         "Use only if asked. Keep answers short and point back to the live demo.")
qa = [("\u201cIsn\u2019t this just another chatbot?\u201d", "No. Answers are computed from a governed graph with provenance; numbers are deterministic. The LLM only phrases the answer."),
      ("\u201cCompliance will block it.\u201d", "Public label data only, guardrails enforced in code, MLR stays in the loop, full audit trail. Designed for audit."),
      ("\u201cWill it scale?\u201d", "Storage already mirrors to Neo4j; ingestion and agents are franchise-agnostic. A new franchise is onboarding data, not a rebuild."),
      ("\u201cWhat does it cost?\u201d", "The POC cost $0 in licences. Pilot spend is mostly people time; productivity alone pays it back.")]
for i, (q, a) in enumerate(qa):
    x, y = 0.6 + (i % 2) * 6.15, 1.75 + (i // 2) * 2.55
    card(s, x, y, 5.98, 2.3)
    rect(s, x, y + 0.3, 0.07, 1.7, [RED, TEAL, GOLD, GREEN][i])
    text(s, x + 0.35, y + 0.28, 5.4, 0.6, q, size=18, font=SERIF)
    text(s, x + 0.35, y + 0.95, 5.35, 1.3, a, size=13, color=MUTED, spacing=1.15)

# 20. Close ------------------------------------------------------------------------------------------
s = prs.slides.add_slide(BLANK)
s.background.fill.solid()
s.background.fill.fore_color.rgb = INK
rect(s, 0, 0, 13.333, 0.07, RED)
text(s, 0.9, 1.7, 11, 0.4, "THANK YOU", size=13, color=GOLD, bold=True)
text(s, 0.9, 2.15, 11.5, 1.6, "One cited knowledge layer.\nEvery franchise. Every claim traceable.", size=40, font=SERIF, color=WHITE, spacing=1.05)
text(s, 0.9, 4.35, 11, 0.5, "Questions & discussion \u2014 and a decision on the 10\u201312 week pilot.", size=18, color=RGBColor(0xB8, 0xC2, 0xD3))
card(s, 0.9, 5.4, 7.6, 1.15, RGBColor(0x16, 0x20, 0x33), None)
text(s, 1.15, 5.52, 7.2, 0.95, [[("Run the demo locally:  ", {"color": RGBColor(0xB8, 0xC2, 0xD3)}), ("npm run dev", {"font": "Consolas", "color": GOLD, "bold": True}),
                                 ("  \u2192  http://localhost:5173", {"color": WHITE})],
                                [("github.com/rshank23/jnj-graphrag-nexus", {"color": RGBColor(0xB8, 0xC2, 0xD3), "size": 12})]], size=15, after=6)
s.notes_slide.notes_text_frame.text = "Close on the ask. Offer a hands-on session with the pilot users' managers."

prs.save(OUT)
print(f"saved {OUT} ({len(prs.slides)} slides)")
