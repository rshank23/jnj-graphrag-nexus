"""Build the 5-slide intro deck (docs/JnJ-GraphRAG-Nexus-Intro.pptx).

Covers: 1) what the POC is, 2) how it improves the current workflow, 3) is it really needed.
Usage:  python docs/demo/build_intro_deck.py
"""
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "JnJ-GraphRAG-Nexus-Intro.pptx"

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


def pill(s, x, y, label, fill=TEAL_SOFT, color=TEAL, size=10.5):
    w = 0.22 + len(label) * 0.085
    card(s, x, y, w, 0.32, fill, None, radius=0.5)
    text(s, x, y, w, 0.32, label, size=size, color=color, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    return w


def base(title, kicker, notes):
    s = prs.slides.add_slide(BLANK)
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = PAGE
    rect(s, 0, 0, 13.333, 0.07, RED)
    text(s, 0.6, 0.42, 10, 0.3, kicker.upper(), size=11, color=TEAL, bold=True)
    text(s, 0.6, 0.68, 12.1, 0.75, title, size=30, font=SERIF)
    _page["n"] += 1
    text(s, 0.6, 7.08, 8, 0.25, [[("J&J ", {"color": RED, "bold": True}), "GraphRAG Nexus  \u00B7  POC intro"]],
         size=9, color=MUTED)
    text(s, 11.73, 7.08, 1.0, 0.25, str(_page["n"]), size=9, color=MUTED, align=PP_ALIGN.RIGHT)
    s.notes_slide.notes_text_frame.text = notes
    return s


def shot(s, name, x, y, w):
    h = w * 9 / 16
    card(s, x - 0.05, y - 0.05, w + 0.1, h + 0.1, radius=0.02)
    s.shapes.add_picture(str(HERE / f"{name}.png"), Inches(x), Inches(y), Inches(w), Inches(h))
    return h


def table(s, x, y, rows, widths, size=11, row_h=0.4, hi_col=None):
    shp = s.shapes.add_table(len(rows), len(rows[0]), Inches(x), Inches(y), Inches(sum(widths)), Inches(row_h * len(rows)))
    tbl = shp.table
    for j, cw in enumerate(widths):
        tbl.columns[j].width = Inches(cw)
    for i, row in enumerate(rows):
        tbl.rows[i].height = Inches(row_h)
        for j, val in enumerate(row):
            c = tbl.cell(i, j)
            c.fill.solid()
            c.fill.fore_color.rgb = INK if i == 0 else (WHITE if i % 2 else ZEBRA)
            c.margin_left = c.margin_right = Inches(0.1)
            c.margin_top = c.margin_bottom = Inches(0.03)
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            c.text_frame.word_wrap = True
            r = c.text_frame.paragraphs[0].add_run()
            r.text = str(val)
            f = r.font
            f.name, f.size = SANS, Pt(size)
            f.color.rgb = WHITE if i == 0 else INK
            f.bold = i == 0 or j == 0
            if hi_col is not None and i > 0 and j == hi_col:
                f.color.rgb, f.bold = TEAL, True
    return tbl


# 1. What is this POC? -------------------------------------------------------------------------------
s = base("One cited knowledge layer for the J&J portfolio", "1 \u00B7 What is this POC?",
         "Opening question: 'Where do our products meet in an AFib procedure, and can we prove every claim?' "
         "Today that takes hours across PI PDFs, IFUs, DailyMed and intranet pages. Nexus connects IM and MedTech "
         "products to procedures, anatomy, conditions and label evidence in one graph, and answers with citations. "
         "Live: Graph Explorer, search CARTO, click the node to show the cross-franchise neighbourhood with evidence.")
text(s, 0.6, 1.55, 6.2, 1.1, "Connects J&J Innovative Medicine and MedTech products to procedures, anatomy, "
     "conditions and regulatory evidence, so questions get answered in seconds, with sources.",
     size=15, color=MUTED, spacing=1.15)
steps = [
    ("SANCTIONED SOURCES", "openFDA, DailyMed, FAERS, GUDID, MAUDE, ClinicalTrials.gov, PubMed, jnj.com"),
    ("KNOWLEDGE GRAPH", "Typed nodes & edges: product \u2192 procedure \u2192 anatomy \u2192 evidence, with provenance"),
    ("GRAPHRAG + AGENTS", "Hybrid search + 2-hop graph traversal; router sends each question to a specialist agent"),
    ("CITED ANSWERS", "Bundles, Q&A and MLR pre-review, every fact traced to its label of record"),
]
for i, (head, body) in enumerate(steps):
    y = 2.75 + i * 0.98
    card(s, 0.6, y, 6.2, 0.85)
    card(s, 0.6, y, 0.12, 0.85, RED if i == 3 else TEAL, None, radius=0.3)
    text(s, 0.9, y + 0.1, 5.8, 0.3, head, size=10.5, color=TEAL, bold=True)
    text(s, 0.9, y + 0.38, 5.8, 0.45, body, size=12)
shot(s, "02-graph-carto-spotlight", 7.2, 1.6, 5.5)
text(s, 7.2, 4.8, 5.5, 0.3, "Graph Explorer: CARTO 3 System spotlight across franchises", size=10, color=MUTED,
     align=PP_ALIGN.CENTER)
px = 7.2
for lbl, f, c in [("Every answer cited", GREEN_SOFT, GREEN), ("Kenvue-safe", RED_SOFT, RED),
                  ("$0 licence \u00B7 runs offline", GOLD_SOFT, GOLD)]:
    px += pill(s, px, 5.35, lbl, f, c) + 0.12
text(s, 7.2, 5.9, 5.5, 0.9, "Five workspaces on one graph: Graph Explorer \u00B7 Cross-Sell Bundler \u00B7 Agent Co-Pilot "
     "\u00B7 MLR Pre-Review \u00B7 Sources & Ops", size=11.5, color=MUTED)

# 2. How it improves the current workflow ------------------------------------------------------------
s = base("From hours of siloed searching to seconds, with provenance", "2 \u00B7 How it improves today\u2019s workflow",
         "Walk the table row by row and demo each one live: Co-Pilot Regulatory Auditor preset; Bundler AFib at 500/yr; "
         "MLR Pre-Review with the non-compliant sample; ingest 'Tylenol' to show the Kenvue rejection. "
         "Key message: answers are computed from a governed graph, not generated from LLM memory. "
         "Bundle prices are illustrative list prices.")
table(s, 0.6, 1.6, [
    ["Task", "Today", "With Nexus"],
    ["Which products are used in procedure X, and what supports them?",
     "Manual search across PI/IFU PDFs, DailyMed, intranet (hours)", "Seconds, with citations and claim-provenance table"],
    ["Cross-franchise selling", "Reps know their own bag; same-procedure opportunities missed",
     "Full-procedure bill of materials: AFib @ 500/yr: $451k capital \u2192 ~$2.8M year 1"],
    ["MLR claim checks", "Line-by-line reading against the label (main bottleneck)",
     "10 automated checks flag issues + suggested rewrites before human review"],
    ["Kenvue boundary", "Relies on people noticing", "Enforced in code: \u2018Tylenol\u2019 rejected, 0 nodes added"],
    ["Keeping knowledge current", "Ad hoc", "Tracked source syncs + label-change alerts"],
], [3.3, 4.0, 4.8], size=11.5, row_h=0.62, hi_col=2)
card(s, 0.6, 5.6, 12.1, 1.25, TEAL_SOFT, None)
text(s, 0.85, 5.72, 11.6, 0.3, "WHY NOT JUST A CHATBOT?", size=10.5, color=TEAL, bold=True)
text(s, 0.85, 6.02, 11.6, 0.8, [[("Plain LLM / vector RAG: ", {"bold": True}),
     "hallucinated numbers, chunk-level citations, no multi-hop reasoning.  ",
     ("Nexus: ", {"bold": True, "color": RED}),
     "numbers computed from the graph, every claim traced to a label, guardrails enforced in code. "
     "The LLM is optional; it only phrases the answer."]], size=12.5, spacing=1.15)

# 2b. Real-world examples ---------------------------------------------------------------------------
s = base("Real-world examples: before and after", "2 \u00B7 How it improves today\u2019s workflow: in practice",
         "Pick the one or two examples most relevant to the audience and demo them live. "
         "1) KAM: Bundler, AFib at 500/yr, export the DOCX proposal. 2) MSL: Co-Pilot question about CARVYKTI; show "
         "cited label sections. 3) MLR: paste the non-compliant TREMFYA sample; show findings and rewrites. "
         "4) Label change: Sources & Ops, sync openfda_label, show LabelChange nodes. "
         "Time estimates are indicative; the pilot will baseline them with real users.")
COLS = [(0.6, 3.0), (3.75, 4.35), (8.25, 4.45)]
for (x, w), head, c in zip(COLS, ["WHO \u00B7 SCENARIO", "BEFORE (TODAY)", "NOW (WITH NEXUS)"], [MUTED, GOLD, GREEN]):
    text(s, x + 0.15, 1.5, w, 0.3, head, size=10.5, color=c, bold=True)
examples = [
    ("Key account manager", "Hospital capital committee for an AFib ablation programme",
     "Collect price lists from EP, imaging and Ethicon teams by email; build the bill of materials in Excel",
     "1\u20132 days",
     "Bundler: pick AFib, set 500 procedures/yr \u2192 4-tier bill of materials + ROI \u2192 export DOCX proposal",
     "~5 min"),
    ("Medical science liaison", "HCP asks: \u201cCARVYKTI boxed warnings and supporting trial data?\u201d",
     "Search DailyMed, download the PI PDF, read sections, cross-check FAERS and ClinicalTrials.gov",
     "2\u20134 hrs",
     "Co-Pilot: ask the question \u2192 answer citing label sections, trials and safety signals",
     "Seconds"),
    ("Marketing / MLR reviewer", "Promotional email for TREMFYA before committee review",
     "Read every claim line by line against the PI; several revise-and-resubmit cycles",
     "Days\u2013weeks",
     "MLR Pre-Review: flags absolute and off-label claims, suggests rewrites, cites precedents \u2192 DOCX",
     "Minutes"),
    ("Regulatory / content owner", "FDA updates a label; which live content is affected?",
     "Someone notices the change, then manually searches all materials that mention the product",
     "Often missed",
     "Label-change monitor diffs label sections \u2192 LabelChange node \u2192 affected claims flagged",
     "Automatic"),
]
for i, (who, scen, before, t_before, now, t_now) in enumerate(examples):
    y = 1.88 + i * 1.22
    card(s, 0.6, y, 12.1, 1.1, WHITE if i % 2 == 0 else ZEBRA)
    text(s, 0.75, y + 0.12, 2.85, 0.3, who.upper(), size=10, color=TEAL, bold=True)
    text(s, 0.75, y + 0.4, 2.85, 0.7, scen, size=11.5, bold=True)
    card(s, 3.75, y + 0.1, 4.35, 0.9, GOLD_SOFT, None)
    text(s, 3.9, y + 0.17, 2.75, 0.8, before, size=11, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 6.85, y + 0.1, 1.15, 0.9, t_before, size=13, color=GOLD, bold=True, align=PP_ALIGN.RIGHT,
         anchor=MSO_ANCHOR.MIDDLE)
    card(s, 8.25, y + 0.1, 4.35, 0.9, GREEN_SOFT, None)
    text(s, 8.4, y + 0.17, 3.1, 0.8, now, size=11, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 11.45, y + 0.1, 1.05, 0.9, t_now, size=13, color=GREEN, bold=True, align=PP_ALIGN.RIGHT,
         anchor=MSO_ANCHOR.MIDDLE)
text(s, 0.6, 6.78, 12.1, 0.25, "Time estimates are indicative; the pilot baselines them with real users.",
     size=9.5, color=MUTED, align=PP_ALIGN.RIGHT)

# 3. Proof it works ---------------------------------------------------------------------------------
s = base("Working software, measured, not just slides", "2 \u00B7 How it improves today\u2019s workflow: proof",
         "Numbers come from docs/EVAL.md (40-query golden set, k=5). Recall is high for all methods; the real gain is "
         "ranking: GraphRAG puts the right answer first (MRR 0.975 vs 0.68 for keyword search). "
         "Groundedness 1.0 means every answer carried citations. CI fails if GraphRAG drops below the regression gate.")
stats = [("0.975", "GraphRAG MRR\nvs 0.68 keyword \u00B7 0.57 vector", RED),
         ("0.99", "Recall@5 on 40-question\ngolden set", TEAL),
         ("100%", "Answers grounded\nwith citations", GREEN),
         ("0.975", "Agent routing\naccuracy", TEAL)]
for i, (num, lbl, c) in enumerate(stats):
    x = 0.6 + i * 3.07
    card(s, x, 1.6, 2.87, 1.45)
    text(s, x + 0.25, 1.72, 2.5, 0.65, num, size=32, font=SERIF, color=c)
    text(s, x + 0.25, 2.4, 2.5, 0.6, lbl, size=11, color=MUTED)
for i, (img, cap) in enumerate([("03-bundler", "Cross-Sell Bundler"), ("04b-copilot-claims", "Co-Pilot claim audit"),
                                ("05b-mlr-findings", "MLR Pre-Review findings")]):
    x = 0.6 + i * 4.1
    shot(s, img, x, 3.35, 3.9)
    text(s, x, 5.65, 3.9, 0.3, cap, size=10.5, color=MUTED, bold=True, align=PP_ALIGN.CENTER)
text(s, 0.6, 6.2, 12.1, 0.6, "57 automated offline tests \u00B7 open-source stack (FastAPI, LangGraph, NetworkX/Neo4j, React) "
     "\u00B7 audit hash-chain \u00B7 role-based access \u00B7 MCP server so other teams\u2019 assistants can query the graph",
     size=11.5, color=MUTED, align=PP_ALIGN.CENTER)

# 4. Is it really needed? ---------------------------------------------------------------------------
s = base("Is it really needed? Yes, and it is cheap to prove", "3 \u00B7 Is it really needed?",
         "Be honest here; it builds credibility. Why yes: the value lives in connections no single franchise owns, "
         "it reduces compliance risk, and the POC cost $0 in licences. Even 20% of the illustrative productivity "
         "estimate (~$2.17M/yr in PITCH.md) covers a typical pilot budget. Then name the limits openly, and close "
         "with a small, measurable pilot ask.")
cols = [
    ("WHY YES", GREEN, GREEN_SOFT, [
        [("Connections no franchise owns: ", {"bold": True}), "procedure-centric, IM \u00D7 MedTech pathways"],
        [("Lower compliance risk: ", {"bold": True}), "fewer outdated / off-label claims reach MLR; full audit trail"],
        [("Cheap to prove: ", {"bold": True}), "$0 licence; 20% of the productivity estimate covers a pilot"],
        [("Reusable: ", {"bold": True}), "a new franchise is data onboarding, not a new build"],
    ]),
    ("WHAT IT IS NOT (YET)", GOLD, GOLD_SOFT, [
        [("Prices are illustrative: ", {"bold": True}), "pilot needs SAP / product-master data"],
        [("MedTech scraping blocked: ", {"bold": True}), "move to GUDID / internal master"],
        [("Not an MLR replacement: ", {"bold": True}), "a pre-screen; humans stay in the loop"],
        [("Time savings are estimates ", {"bold": True}), "until baselined with real users"],
    ]),
    ("THE ASK: A SMALL PILOT", RED, RED_SOFT, [
        [("Scope: ", {"bold": True}), "EP / AFib + 1 IM therapeutic area, 1 region"],
        [("Users: ", {"bold": True}), "~20 reps, 5 MSLs, 2\u20133 MLR reviewers"],
        [("Time: ", {"bold": True}), "10\u201312 weeks"],
        [("Exit KPIs: ", {"bold": True}), "groundedness \u2265 95%, time-to-answer \u221270%, MLR flag precision \u2265 80%"],
    ]),
]
for i, (head, c, soft, items) in enumerate(cols):
    x = 0.6 + i * 4.1
    card(s, x, 1.6, 3.9, 4.75)
    rect(s, x, 1.6, 3.9, 0.08, c)
    card(s, x + 0.25, 1.88, 3.4, 0.4, soft, None, radius=0.5)
    text(s, x + 0.25, 1.88, 3.4, 0.4, head, size=11, color=c, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    bullets(s, x + 0.25, 2.55, 3.45, 3.8, items, size=14.5, marker=c, after=16)
text(s, 0.6, 6.5, 12.1, 0.4, [[("Bottom line: ", {"bold": True, "color": RED}),
     "the problem is real and spread across functions; the POC shows it is solvable; a 12-week pilot proves the value with numbers."]],
     size=13, align=PP_ALIGN.CENTER)

prs.save(OUT)
print(f"Saved {OUT}")
