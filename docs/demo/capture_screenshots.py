import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
URL = "http://localhost:5173/"


def shot(page, name):
    page.screenshot(path=str(OUT / f"{name}.png"))
    print("saved", name)


def tab(page, label):
    page.get_by_role("button", name=label).first.click()
    page.wait_for_timeout(1500)


def click_node(page, want="CARTO 3 System V8"):
    import math
    canvas = page.locator("main canvas").first
    box = canvas.bounding_box()
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    tried = []
    for r in range(0, 420, 5):
        for a in range(0, 360, 8):
            x, y = cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))
            if y > 895 or any(abs(x - tx) < 18 and abs(y - ty) < 18 for tx, ty in tried):
                continue
            page.mouse.move(x, y)
            if canvas.evaluate("c => c.style.cursor") == "pointer":
                tried.append((x, y))
                page.mouse.click(x, y)
                page.wait_for_timeout(900)
                txt = page.locator("main aside").last.inner_text()
                if txt.startswith("Product") and want in txt:
                    return (x, y)
    return None

with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge")
    page = b.new_page(viewport={"width": 1600, "height": 900}, device_scale_factor=1.5)
    page.goto(URL)
    page.wait_for_timeout(6000)
    shot(page, "01-graph-overview")

    page.fill('input[placeholder^="CARTO"]', "CARTO")
    page.wait_for_timeout(3500)
    page.locator('button[title="Fit graph"]').click()
    page.wait_for_timeout(1200)
    print("node click at", click_node(page))
    page.locator("main").first.scroll_into_view_if_needed()
    page.evaluate("window.scrollTo(0, document.querySelector('main').getBoundingClientRect().top + window.scrollY - 20)")
    page.wait_for_timeout(600)
    shot(page, "02-graph-carto-spotlight")
    page.evaluate("window.scrollTo(0,0)")

    tab(page, "Cross-Sell Bundler")
    page.wait_for_timeout(2500)
    shot(page, "03-bundler")
    page.evaluate("window.scrollTo(0, 650)")
    page.wait_for_timeout(500)
    shot(page, "03b-bundler-detail")
    page.evaluate("window.scrollTo(0,0)")

    tab(page, "Agent Co-Pilot")
    page.get_by_text("Regulatory Auditor", exact=True).first.click()
    page.wait_for_timeout(9000)
    shot(page, "04-copilot")
    page.evaluate("window.scrollTo(0, 700)")
    page.wait_for_timeout(500)
    shot(page, "04b-copilot-claims")
    page.evaluate("window.scrollTo(0,0)")

    tab(page, "MLR Pre-Review")
    page.get_by_role("button", name="Non-compliant draft").click()
    page.get_by_role("button", name="Run pre-review").click()
    page.wait_for_timeout(5000)
    shot(page, "05-mlr")
    page.evaluate("window.scrollTo(0, 600)")
    page.wait_for_timeout(500)
    shot(page, "05b-mlr-findings")
    page.evaluate("window.scrollTo(0,0)")

    tab(page, "Sources & Ops")
    page.get_by_role("button", name="Run eval").click()
    page.wait_for_timeout(15000)
    shot(page, "06-ops")
    page.evaluate("window.scrollTo(0, 650)")
    page.wait_for_timeout(500)
    shot(page, "06b-ops-eval")
    page.evaluate("window.scrollTo(0,0)")

    tab(page, "Knowledge Graph")
    page.get_by_role("button", name="Sync live J&J / FDA data").click()
    page.wait_for_timeout(1000)
    page.get_by_role("button", name="FDA DailyMed").click()
    page.fill('input[placeholder^="e.g. CARVYKTI"]', "Tylenol")
    page.get_by_role("button", name="Run Ingestion").click()
    page.wait_for_timeout(6000)
    shot(page, "07-kenvue-guardrail")
    b.close()
