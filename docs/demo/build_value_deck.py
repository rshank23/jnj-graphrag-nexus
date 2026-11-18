"""Build the 3-slide value deck (docs/JnJ-GraphRAG-Nexus-Value.pptx).

Slide 1: B2B benefits for J&J and its customers. Slide 2: real-world B2B before/after examples.
Slide 3: how it differs from a chatbot and supports it.
Usage:  python docs/demo/build_value_deck.py
"""
import sys
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

HERE = Path(__file__).resolve().parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "JnJ-GraphRAG-Nexus-Value.pptx"

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


def base(title, kicker, notes):
    s = prs.slides.add_slide(BLANK)
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = PAGE
    rect(s, 0, 0, 13.333, 0.07, RED)
    text(s, 0.6, 0.38, 10, 0.3, kicker.upper(), size=11, color=TEAL, bold=True)
    text(s, 0.6, 0.64, 12.1, 0.7, title, size=28, font=SERIF)
    _page["n"] += 1
    text(s, 0.6, 7.1, 8, 0.25, [[("J&J ", {"color": RED, "bold": True}), "GraphRAG Nexus  \u00B7  Value for J&J"]],
         size=9, color=MUTED)
    text(s, 11.73, 7.1, 1.0, 0.25, str(_page["n"]), size=9, color=MUTED, align=PP_ALIGN.RIGHT)
    s.notes_slide.notes_text_frame.text = notes
    return s


def arrow(s, x1, y1, x2, y2, color=TEAL):
    c = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = color
    c.line.width = Pt(2)
    ln = c.line._get_or_add_ln()
    ln.append(ln.makeelement("{http://schemas.openxmlformats.org/drawingml/2006/main}tailEnd", {"type": "triangle"}))
    return c


# 1. How Nexus benefits J&J and its B2B customers -----------------------------------------------------
s = base("Better for J&J\u2019s customers, cheaper for J&J to serve", "Value in a B2B model \u00B7 hospitals, IDNs, GPOs, payers, HCPs",
         "J&J sells to institutions: hospital value analysis committees, IDNs/GPOs, P&T committees, payers and HCPs. "
         "Every card = a customer moment that gets faster or cheaper. "
         "1) Bundler AFib @ 500/yr: $451k capital + $4,695 per case, with compatibility and evidence (illustrative prices). "
         "2) Same bundle: ~$2.8M year 1 vs $451k capital-only. "
         "3) Eval: MRR 0.975 vs 0.57 for vector search; cited label/IFU/trial answers for MSLs and Medical Info. "
         "4) MLR Pre-Review: TREMFYA draft 3 critical + 3 warnings, corrected version risk 0. "
         "5) Recall and label syncs create Recall / LabelChange nodes linked to products and procedures. "
         "6) Commercial role + 'Can TREMFYA be used for multiple myeloma?' is blocked in code; audit log is hash-chained.")
benefits = [
    ("1", "Faster hospital buying decisions", GREEN, GREEN_SOFT,
     "Value analysis committees get one cited, procedure-level quote (capital + per-case cost) instead of separate franchise quotes.",
     "Proof: AFib = $451k capital + $4,695/case", "KPI: days from customer request to quote"),
    ("2", "Bigger, stickier accounts", GREEN, GREEN_SOFT,
     "One procedure view links EP, Ethicon and imaging products, so one account team sells the whole procedure.",
     "Proof: AFib @ 500 cases \u2192 ~$2.8M year 1", "KPI: attach rate, revenue per account"),
    ("3", "Quicker answers to HCPs", TEAL, TEAL_SOFT,
     "MSLs and Medical Information answer hospital and HCP questions with label, IFU and trial citations in minutes.",
     "Proof: MRR 0.975 vs 0.57 for vector search", "KPI: inquiry turnaround time"),
    ("4", "Customer material approved sooner", GOLD, GOLD_SOFT,
     "Payer decks, hospital value dossiers and HCP materials are pre-screened before MLR, so fewer costly review rounds.",
     "Proof: 6 issues caught \u2192 fixed draft risk 0", "KPI: MLR rounds and days per asset"),
    ("5", "Faster recall & label response", TEAL, TEAL_SOFT,
     "FDA recalls and label changes are linked to the products and procedures they affect, so the right customers hear first.",
     "Proof: Recall / LabelChange nodes in graph", "KPI: hours to customer notification"),
    ("6", "Compliant at every touchpoint", RED, RED_SOFT,
     "Reps cannot give off-label answers to customers; those questions route to Medical. Every answer is logged.",
     "Proof: off-label query blocked for Commercial", "KPI: 0 off-label incidents"),
]
W, H = 3.92, 2.45
for i, (num, head, c, soft, body, proof, kpi) in enumerate(benefits):
    x = 0.6 + (i % 3) * (W + 0.17)
    y = 1.55 + (i // 3) * (H + 0.17)
    card(s, x, y, W, H)
    rect(s, x, y, W, 0.07, c)
    card(s, x + 0.22, y + 0.25, 0.46, 0.46, soft, None, radius=0.5)
    text(s, x + 0.22, y + 0.25, 0.46, 0.46, num, size=15, color=c, bold=True, font=SERIF,
         align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    text(s, x + 0.82, y + 0.25, W - 1.0, 0.46, head, size=15.5, bold=True, anchor=MSO_ANCHOR.MIDDLE)
    text(s, x + 0.22, y + 0.85, W - 0.42, 0.95, body, size=11.5, color=INK, spacing=1.1)
    text(s, x + 0.22, y + 1.72, W - 0.42, 0.3, proof, size=10.5, color=c, bold=True)
    text(s, x + 0.22, y + 2.02, W - 0.42, 0.3, kpi, size=10, color=MUTED)
text(s, 0.6, 6.72, 12.1, 0.3, [[("In one line: ", {"bold": True, "color": RED}),
     "customers decide faster with cited facts; J&J wins bigger accounts at a lower cost to serve."]],
     size=12.5, align=PP_ALIGN.CENTER)

# 2. Real-world B2B examples --------------------------------------------------------------------------
s = base("Real-world B2B moments: before vs with Nexus", "How it improves the customer experience and cuts cost",
         "Pick one or two rows to tell as a story. Row 1 is the live demo (Bundler, AFib). "
         "Row 2: switch to the Medical role and ask about CARVYKTI safety. Row 3: MLR Pre-Review on the TREMFYA sample. "
         "Row 4: show a Recall or LabelChange node linked to its product. "
         "'Before' times are typical industry experience, not J&J measurements; the pilot should baseline them.")
ex_rows = [
    ("Customer moment", "Before (today)", "With Nexus", "Impact"),
    ([("Hospital value analysis committee", {"bold": True}), ("\nEvaluating a new AFib ablation program (MedTech EP)", {"color": MUTED})],
     "Rep gathers separate quotes from EP, Ethicon and imaging; checks compatibility by hand; weeks of back-and-forth.",
     "Bundler returns the whole procedure: CARTO 3 V8 + modules, VIZIGO, AcuNav, BIOPATCH, with compatibility and cited evidence.",
     [("Experience: ", {"bold": True}), "one clear quote in minutes\n", ("Cost: ", {"bold": True}),
      "fewer wrong-SKU orders; $451k + $4,695/case visible upfront"]),
    ([("Oncology center P&T committee", {"bold": True}), ("\nAssessing CARVYKTI safety before adding it to formulary", {"color": MUTED})],
     "Medical Information request; MSL searches label, trials, PubMed and FAERS by hand; answer in days.",
     "Medical role gets a cited answer: boxed warning, REMS and indication from the FDA label, plus synced trials and FAERS signals.",
     [("Experience: ", {"bold": True}), "faster formulary decision\n", ("Cost: ", {"bold": True}),
      "less MSL search time; consistent answers"]),
    ([("Payer / IDN contracting", {"bold": True}), ("\nTREMFYA value deck for a formulary or contract review", {"color": MUTED})],
     "Marketing drafts, MLR finds cure claims or off-label lines late, and the deck goes through several rounds.",
     "Pre-Review flags the cure claim, off-label myeloma and comparative claims, with rewrites, before MLR submission.",
     [("Experience: ", {"bold": True}), "customer gets material sooner\n", ("Cost: ", {"bold": True}),
      "fewer review rounds and agency revisions"]),
    ([("Hospital biomed & supply chain", {"bold": True}), ("\nAn FDA recall or label change hits an installed product", {"color": MUTED})],
     "Regulatory reads the notice and emails franchises; teams build affected-product and material lists manually.",
     "Recall / LabelChange is linked to the product, its procedures and bundles, giving an impact list right away.",
     [("Experience: ", {"bold": True}), "right hospitals told first\n", ("Cost: ", {"bold": True}),
      "less safety and liability exposure"]),
]
widths = [2.75, 3.2, 3.55, 2.6]
shp = s.shapes.add_table(len(ex_rows), 4, Inches(0.6), Inches(1.5), Inches(sum(widths)), Inches(5.0))
tbl = shp.table
for j, cw in enumerate(widths):
    tbl.columns[j].width = Inches(cw)
for i, row in enumerate(ex_rows):
    tbl.rows[i].height = Inches(0.45 if i == 0 else 1.15)
    for j, val in enumerate(row):
        cell = tbl.cell(i, j)
        cell.fill.solid()
        cell.fill.fore_color.rgb = INK if i == 0 else (WHITE if i % 2 else ZEBRA)
        cell.margin_left = cell.margin_right = Inches(0.1)
        cell.margin_top = cell.margin_bottom = Inches(0.05)
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        cell.text_frame.word_wrap = True
        p = cell.text_frame.paragraphs[0]
        p.line_spacing = 1.05
        for seg in (val if isinstance(val, list) else [val]):
            t, o = (seg, {}) if isinstance(seg, str) else seg
            r = p.add_run()
            r.text = t
            f = r.font
            f.name, f.size = SANS, Pt(11 if i == 0 else 10.5)
            f.bold = i == 0 or o.get("bold", False)
            f.color.rgb = WHITE if i == 0 else o.get("color", GREEN if j == 3 else (MUTED if j == 1 else INK))
text(s, 0.6, 6.72, 12.1, 0.3, [[("Pattern: ", {"bold": True, "color": RED}),
     "every B2B customer moment that waits on a person searching documents gets faster, cheaper and cited."]],
     size=12.5, align=PP_ALIGN.CENTER)
text(s, 0.6, 6.98, 12.1, 0.2, "\u2018Before\u2019 reflects typical industry workflows; prices are illustrative. Baseline both in the pilot.",
     size=8.5, color=MUTED, align=PP_ALIGN.CENTER)

# 3. Not a chatbot: the knowledge layer under it ------------------------------------------------------
s = base("Not another chatbot: the governed layer that makes chatbots safe", "Chatbot vs Nexus \u00B7 complement, not competitor",
         "Open with: 'A chatbot gives a plausible answer; Nexus gives the complete, current and permitted answer, "
         "and can prove it.' Walk the table, then the diagram: keep Copilot / ChatGPT Enterprise as the interface; "
         "Nexus plugs in underneath via MCP (graph_search, procedural_bundle, mlr_review, agent_query). "
         "Live proof: same TREMFYA x myeloma question as Commercial (blocked) vs Medical (cited answer). "
         "Objection 'better prompts?': a prompt is a request, code is enforcement.")
table_rows = [
    ("", "Normal chatbot", "GraphRAG Nexus"),
    ("Who is asking?", "Answers anyone; rules live in a prompt", "Role-based gates enforced in code"),
    ("Multi-hop questions", "Finds similar text; misses links", "Traverses product \u2192 procedure \u2192 label"),
    ("Completeness", "Top 5\u201310 similar chunks", "Every connected node and claim"),
    ("Current label?", "Training cutoff; no version diff", "Synced sources + label-change diff"),
    ("Numbers (price, ROI)", "Can be invented", "Computed from graph data"),
    ("Repeatability / audit", "Varies run to run", "Same evidence, cited, hash-chained log"),
    ("Retrieval quality (MRR)", "0.57 (vector search)", "0.975 (GraphRAG)"),
]
shp = s.shapes.add_table(len(table_rows), 3, Inches(0.6), Inches(1.55), Inches(7.35), Inches(0.56 * len(table_rows)))
tbl = shp.table
for j, cw in enumerate([2.05, 2.55, 2.75]):
    tbl.columns[j].width = Inches(cw)
for i, row in enumerate(table_rows):
    tbl.rows[i].height = Inches(0.56)
    for j, val in enumerate(row):
        cell = tbl.cell(i, j)
        cell.fill.solid()
        cell.fill.fore_color.rgb = INK if i == 0 else (WHITE if i % 2 else ZEBRA)
        cell.margin_left = cell.margin_right = Inches(0.1)
        cell.margin_top = cell.margin_bottom = Inches(0.03)
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        cell.text_frame.word_wrap = True
        r = cell.text_frame.paragraphs[0].add_run()
        r.text = val
        f = r.font
        f.name, f.size = SANS, Pt(11)
        f.bold = i == 0 or j == 0 or j == 2
        f.color.rgb = WHITE if i == 0 else (MUTED if j == 1 else (GREEN if j == 2 else INK))

# Right: chatbot on top of Nexus
X, CW = 8.3, 4.4
text(s, X, 1.5, CW, 0.3, "HOW IT FITS: NEXUS POWERS THE CHATBOT", size=10.5, color=TEAL, bold=True)
card(s, X, 1.9, CW, 0.95, GOLD_SOFT, None)
text(s, X + 0.2, 1.98, CW - 0.4, 0.8, [[("Chatbot / Copilot / Teams", {"bold": True, "size": 13.5})],
     [("Users keep the interface they already know", {"size": 10.5, "color": MUTED})]], anchor=MSO_ANCHOR.MIDDLE)
arrow(s, X + CW / 2, 2.88, X + CW / 2, 3.33)
text(s, X + CW / 2 + 0.12, 2.93, 2.2, 0.3, "asks via MCP", size=10, color=TEAL, bold=True)
card(s, X, 3.38, CW, 1.75, TEAL_SOFT, TEAL)
text(s, X + 0.2, 3.46, CW - 0.4, 0.35, "GraphRAG Nexus: governed knowledge layer", size=13, bold=True, color=TEAL)
for k, lbl in enumerate(["Knowledge graph", "Role gates", "MLR checks", "Label monitor", "Audit log", "Bundle math"]):
    px = X + 0.2 + (k % 3) * 1.35
    py = 3.9 + (k // 3) * 0.55
    card(s, px, py, 1.25, 0.42, WHITE, None, radius=0.4)
    text(s, px, py, 1.25, 0.42, lbl, size=9.5, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
arrow(s, X + CW / 2, 5.13, X + CW / 2, 5.58, GREEN)
text(s, X + CW / 2 + 0.12, 5.18, 2.2, 0.3, "returns", size=10, color=GREEN, bold=True)
card(s, X, 5.63, CW, 0.82, GREEN_SOFT, None)
text(s, X + 0.2, 5.68, CW - 0.4, 0.72, [[("Cited \u00B7 current \u00B7 permitted answer", {"bold": True, "size": 13, "color": GREEN})],
     [("The LLM only phrases it; the facts come from the graph", {"size": 10.5, "color": MUTED})]], anchor=MSO_ANCHOR.MIDDLE)

card(s, 0.6, 6.25, 7.35, 0.62, RED_SOFT, None)
text(s, 0.8, 6.25, 7.0, 0.62, [[("Bottom line: ", {"bold": True, "color": RED}),
     "keep the chatbot as the front door; Nexus makes what it says compliant and provable."]],
     size=12.5, anchor=MSO_ANCHOR.MIDDLE)

prs.save(OUT)
print(f"Saved {OUT}")
