"""Async scraper for J&J Innovative Medicine, J&J MedTech and the NIH DailyMed v2 REST API."""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, Tag

from app.config import get_settings
from app.graph.seed_data import IM, MT, is_kenvue_brand
from app.ingestion.pdf_extractor import resolve_franchise_id, slugify
from app.models.schemas import EdgeType, GraphEdge, GraphNode, NodeType, ScrapedProduct

logger = logging.getLogger(__name__)

IM_PRODUCTS_URL = "https://www.jnj.com/innovativemedicine/our-products"
MT_PRODUCTS_URL = "https://www.jnjmedtech.com/en-US/products/all-products/"
DAILYMED_SPLS_URL = "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json"
DAILYMED_PDF_URL = "https://dailymed.nlm.nih.gov/dailymed/downloadpdffile.cfm?setId={setid}"
DAILYMED_LABEL_URL = "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={setid}"
USER_AGENT = "Mozilla/5.0 (compatible; JnJ-GraphRAG-Nexus/1.0; +https://www.jnj.com)"

THERAPEUTIC_AREAS = ("Oncology", "Immunology", "Neuroscience", "Cardiopulmonary", "Pulmonary Hypertension",
                     "Infectious Diseases", "Cardiovascular", "Hematology")
MEDTECH_SPECIALTIES = {
    "Electrophysiology": ("carto", "ablation", "electrophysiology", "mapping", "arrhythmia", "biosense"),
    "Orthopaedics / DePuy Synthes": ("knee", "hip", "spine", "trauma", "orthopa", "depuy", "velys", "attune", "saw blade"),
    "Surgery / Ethicon": ("suture", "stapler", "ethicon", "wound", "drain", "hemostat", "biopatch", "monocryl"),
    "Interventional Cardiovascular": ("ivl", "lithotripsy", "shockwave", "impella", "coronary", "abiomed"),
    "Vision": ("lens", "iol", "cataract", "acuvue", "tecnis", "vision"),
}
COMPAT_RULES: List[Tuple[re.Pattern[str], str, EdgeType]] = [
    (re.compile(r"\bcarto\s*3\b|\bcarto\b", re.I), "MT_CARTO_3_V8", EdgeType.COMPATIBLE_ACCESSORY),
    (re.compile(r"\bvelys\b", re.I), "MT_VELYS_ROBOT", EdgeType.COMPATIBLE_ACCESSORY),
    (re.compile(r"\bivl generator\b|\bshockwave\b", re.I), "MT_SHOCKWAVE_IVL_GENERATOR", EdgeType.COMPATIBLE_ACCESSORY),
    (re.compile(r"\b3d\s*ct\b|\bct segmentation\b|\bcardiac ct\b", re.I), "ANAT_LEFT_ATRIUM", EdgeType.AUTO_SEGMENTS_3D_CT),
    (re.compile(r"\besophag", re.I), "ANAT_ESOPHAGUS", EdgeType.AUTO_SEGMENTS_3D_CT),
    (re.compile(r"\bzimmer\b", re.I), "COUPLING_ZIMMER", EdgeType.COMPATIBLE_COUPLING),
    (re.compile(r"\bstryker\b", re.I), "COUPLING_STRYKER", EdgeType.COMPATIBLE_COUPLING),
    (re.compile(r"\bconmed\b|\blinvatec\b|\bhall\b", re.I), "COUPLING_CONMED_HALL", EdgeType.COMPATIBLE_COUPLING),
]
_FRANCHISE_ID_BY_NAME = {
    "Electrophysiology": "FR_ELECTROPHYSIOLOGY",
    "Orthopaedics / DePuy Synthes": "FR_ORTHOPAEDICS",
    "Surgery / Ethicon": "FR_SURGERY",
    "Interventional Cardiovascular": "FR_INTERVENTIONAL_CV",
    "Vision": "FR_VISION",
}


def _text(el: Optional[Tag]) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip() if el else ""


def _card_containers(soup: BeautifulSoup) -> List[Tag]:
    selectors = ["[class*=product-card]", "[class*=productCard]", "[class*=product-tile]", "[class*=card]",
                 "article", "li[class*=product]", "div[class*=product]"]
    seen: set[int] = set()
    out: List[Tag] = []
    for sel in selectors:
        for el in soup.select(sel):
            if id(el) in seen:
                continue
            if el.find(["h2", "h3", "h4", "h5", "strong", "a"]):
                seen.add(id(el))
                out.append(el)
    return out


def _parse_product_search_promos(soup: BeautifulSoup, base_url: str) -> Tuple[List[ScrapedProduct], List[str]]:
    """jnj.com 'our-products' renders server-side `bsp-accordion.ProductSearchPromo` cards."""
    products: Dict[str, ScrapedProduct] = {}
    rejected: List[str] = []
    for card in soup.select(".ProductSearchPromo"):
        name = re.sub(r"[®™\ufffd]", "", _text(card.select_one(".ProductSearchPromo-title"))).strip()
        if not name or len(name) > 140:
            continue
        if is_kenvue_brand(name):
            if name not in rejected:
                rejected.append(name)
            continue
        generic_raw = _text(card.select_one(".ProductSearchPromo-description"))
        generic = generic_raw.strip("() ").strip() or None
        tags = [_text(t) for t in card.select(".ProductSearchPromo-tags-item")]
        area = next((t for t in tags if t), None)
        pi_url = None
        for a in card.select(".ProductSearchPromo-downloads a[href]"):
            if "prescribing information" in _text(a).lower() and "espa" not in _text(a).lower():
                pi_url = urljoin(base_url, a["href"])
                break
        card_text = _text(card)
        has_bw = bool(re.search(r"boxed\s+warning", card_text, re.I))
        anchor = card.get("id")
        key = name.upper()
        if key not in products:
            products[key] = ScrapedProduct(name=name, generic_name=generic, division=IM, franchise=area,
                                           description=f"{name} ({generic})" if generic else None, has_boxed_warning=has_bw,
                                           prescribing_info_url=pi_url, source_url=f"{base_url}#{anchor}" if anchor else base_url)
    return list(products.values()), rejected


def parse_innovative_medicine_html(html: str, base_url: str = IM_PRODUCTS_URL) -> Tuple[List[ScrapedProduct], List[str]]:
    """Extract J&J Innovative Medicine products; returns (products, rejected_kenvue_names)."""
    soup = BeautifulSoup(html, "html.parser")
    if soup.select_one(".ProductSearchPromo"):
        return _parse_product_search_promos(soup, base_url)
    products: Dict[str, ScrapedProduct] = {}
    rejected: List[str] = []
    for card in _card_containers(soup) or [soup]:
        heading = card.find(["h2", "h3", "h4", "h5", "strong"])
        raw_name = _text(heading)
        if not raw_name or len(raw_name) > 140:
            continue
        name = raw_name.replace("®", "").replace("™", "").strip()
        if is_kenvue_brand(name):
            if name not in rejected:
                rejected.append(name)
            continue
        card_text = _text(card)
        generic = None
        m = re.search(r"\(([a-z][a-z0-9 \-,]+)\)", card_text)
        if m:
            generic = m.group(1).strip()
        area = next((a for a in THERAPEUTIC_AREAS if a.lower() in card_text.lower()), None)
        pi_url = None
        for a in card.find_all("a", href=True):
            label = (_text(a) + " " + a["href"]).lower()
            if "prescribing" in label or a["href"].lower().endswith(".pdf"):
                pi_url = urljoin(base_url, a["href"])
                break
        has_bw = bool(re.search(r"boxed\s+warning", card_text, re.I))
        brand_like = bool(re.match(r"^[A-Z][A-Z0-9\-]{2,}", name))
        if not (brand_like or pi_url or generic):
            continue
        desc = card_text[len(raw_name):].strip()[:500] or None
        key = name.split("(")[0].strip().upper()
        if key not in products:
            products[key] = ScrapedProduct(name=name, generic_name=generic, division=IM, franchise=area,
                                           description=desc, has_boxed_warning=has_bw, prescribing_info_url=pi_url,
                                           source_url=base_url)
    return list(products.values()), rejected


def _specialty_for(text: str) -> Optional[str]:
    lowered = text.lower()
    best, score = None, 0
    for spec, kws in MEDTECH_SPECIALTIES.items():
        s = sum(1 for k in kws if k in lowered)
        if s > score:
            best, score = spec, s
    return best


def parse_medtech_html(html: str, base_url: str = MT_PRODUCTS_URL) -> Tuple[List[ScrapedProduct], List[str], Optional[str]]:
    """Extract device titles/descriptions/compatibility; returns (products, rejected, next_page_url)."""
    soup = BeautifulSoup(html, "html.parser")
    products: Dict[str, ScrapedProduct] = {}
    rejected: List[str] = []
    for card in _card_containers(soup):
        title = _text(card.find(["h2", "h3", "h4", "h5", "strong"])) or _text(card.find("a"))
        if not title or len(title) > 160 or title.lower() in {"products", "all products", "menu", "search"}:
            continue
        clean_title = title.replace("®", "").replace("™", "").strip()
        if is_kenvue_brand(clean_title):
            if clean_title not in rejected:
                rejected.append(clean_title)
            continue
        desc_el = card.find("p")
        desc = _text(desc_el) or None
        text = f"{clean_title} {desc or ''}"
        compat = sorted({target for pat, target, _ in COMPAT_RULES if pat.search(text)})
        link = card.find("a", href=True)
        url = urljoin(base_url, link["href"]) if link else base_url
        key = clean_title.upper()
        if key not in products:
            products[key] = ScrapedProduct(name=clean_title, division=MT, franchise=_specialty_for(text), description=desc,
                                           source_url=url, compatibility=compat)
    next_url = None
    nxt = soup.find("a", attrs={"rel": "next"}) or soup.find("a", string=re.compile(r"^\s*(next|›|»)\s*$", re.I))
    if nxt and nxt.get("href"):
        next_url = urljoin(base_url, nxt["href"])
    return list(products.values()), rejected, next_url


def scraped_to_graph(products: List[ScrapedProduct]) -> Tuple[List[GraphNode], List[GraphEdge]]:
    """Convert scraped products into schema-constrained graph triplets."""
    nodes: List[GraphNode] = []
    edges: List[GraphEdge] = []
    for p in products:
        if is_kenvue_brand(p.name):
            continue
        prefix = "SCR_IM_" if p.division == IM else "SCR_MT_"
        pid = prefix + slugify(p.name.split("(")[0])
        props: Dict[str, Any] = {"source_url": p.source_url, "scraped": True, "category": "Scraped Product"}
        if p.generic_name:
            props["generic_name"] = p.generic_name
        if p.description:
            props["clinical_claim" if p.division == MT else "indication"] = p.description
        if p.prescribing_info_url:
            props["prescribing_info_url"] = p.prescribing_info_url
        if p.has_boxed_warning:
            props["boxed_warning"] = "Boxed Warning present - see Full Prescribing Information"
        label = NodeType.SoftwareModule if re.search(r"\bmodule\b|\bsoftware\b", p.name, re.I) else NodeType.Product
        nodes.append(GraphNode(id=pid, label=label, name=p.name, division=p.division, franchise=p.franchise, properties=props))
        fid = _FRANCHISE_ID_BY_NAME.get(p.franchise or "") or resolve_franchise_id(p.franchise, p.description or "")
        if fid:
            edges.append(GraphEdge(source=pid, target=fid, relation=EdgeType.IN_FRANCHISE))
        if p.has_boxed_warning:
            bw_id = "BW_" + slugify(p.name.split("(")[0]) + "_SCR"
            nodes.append(GraphNode(id=bw_id, label=NodeType.BoxedWarning, name=f"Boxed Warning: {p.name.split('(')[0].strip()}",
                                   division=p.division, properties={"warning_text": props["boxed_warning"]}))
            edges.append(GraphEdge(source=pid, target=bw_id, relation=EdgeType.HAS_BOXED_WARNING))
        for target in p.compatibility:
            rel = next(r for _, t, r in COMPAT_RULES if t == target)
            if label == NodeType.SoftwareModule and target == "MT_CARTO_3_V8":
                rel = EdgeType.INTEGRATES_WITH
            edges.append(GraphEdge(source=pid, target=target, relation=rel, properties={"source": "jnjmedtech.com scrape"}))
    return nodes, edges


def _brand_key(name: str) -> str:
    return re.sub(r"[^A-Z0-9]+", " ", name.split("(")[0].upper()).strip()


def reconcile_with_existing(nodes: List[GraphNode], edges: List[GraphEdge],
                            existing: Iterable[Tuple[str, Dict[str, Any]]]) -> Tuple[List[GraphNode], List[GraphEdge]]:
    """Fold scraped products that already exist (same brand) into their curated nodes as enrichment-only updates.

    Curated name/label/franchise/category are preserved; only provenance properties are added.
    `existing` yields (node_id, node_attrs) pairs from the graph store.
    """
    by_brand: Dict[str, Tuple[str, Dict[str, Any]]] = {}
    for nid, attrs in existing:
        if attrs.get("label") in (NodeType.Product.value, NodeType.SoftwareModule.value) and not attrs.get("properties", {}).get("scraped"):
            by_brand.setdefault(_brand_key(attrs.get("name", "")), (nid, attrs))
    remap: Dict[str, str] = {}
    out_nodes: List[GraphNode] = []
    for n in nodes:
        match = by_brand.get(_brand_key(n.name)) if n.label in (NodeType.Product.value, NodeType.SoftwareModule.value) else None
        if match is None:
            out_nodes.append(n)
            continue
        nid, attrs = match
        remap[n.id] = nid
        cur = attrs.get("properties", {})
        enrich = {k: n.properties[k] for k in ("prescribing_info_url",) if k in n.properties}
        enrich["jnj_source_url"] = n.properties.get("source_url")
        if "generic_name" in n.properties and "generic_name" not in cur:
            enrich["generic_name"] = n.properties["generic_name"]
        out_nodes.append(GraphNode(id=nid, label=attrs["label"], name=attrs["name"], division=attrs.get("division"),
                                   franchise=attrs.get("franchise"), properties=enrich))
    # Curated nodes already carry franchise / boxed-warning structure; drop the scraped duplicates of those edges.
    dropped_bw = {e.target for e in edges if e.source in remap and e.relation == EdgeType.HAS_BOXED_WARNING.value}
    out_nodes = [n for n in out_nodes if n.id not in dropped_bw]
    out_edges = [GraphEdge(source=remap.get(e.source, e.source), target=e.target, relation=e.relation, properties=e.properties)
                 for e in edges
                 if not (e.source in remap and e.relation in (EdgeType.IN_FRANCHISE.value, EdgeType.HAS_BOXED_WARNING.value))]
    return out_nodes, out_edges


def http_verify() -> Any:
    """Prefer the OS trust store (corporate TLS-inspection roots) when `truststore` is installed; else certifi."""
    try:
        import ssl

        import truststore

        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except Exception:
        return True


class JnJIngestionScraper:
    def __init__(self, client: Optional[httpx.AsyncClient] = None, timeout: Optional[float] = None):
        self._client = client
        self._timeout = timeout or get_settings().http_timeout_seconds

    async def _get(self, url: str, params: Optional[Dict[str, Any]] = None) -> httpx.Response:
        if self._client is not None:
            resp = await self._client.get(url, params=params)
        else:
            async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True, verify=http_verify(),
                                         headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US"}) as client:
                resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp

    async def scrape_innovative_medicine(self) -> Dict[str, Any]:
        resp = await self._get(IM_PRODUCTS_URL)
        products, rejected = parse_innovative_medicine_html(resp.text, str(resp.url))
        return {"source": IM_PRODUCTS_URL, "products": products, "rejected_kenvue_brands": rejected}

    async def resolve_dailymed_spl(self, drug_name: str) -> Optional[Dict[str, Any]]:
        if is_kenvue_brand(drug_name):
            raise ValueError(f"'{drug_name}' is a Kenvue consumer-health brand")
        resp = await self._get(DAILYMED_SPLS_URL, params={"drug_name": drug_name, "pagesize": 1})
        data = resp.json().get("data") or []
        if not data:
            return None
        rec = data[0]
        setid = rec.get("setid") or rec.get("spl_setid")
        return {
            "drug_name": drug_name,
            "spl_setid": setid,
            "title": rec.get("title"),
            "published_date": rec.get("published_date"),
            "spl_version": rec.get("spl_version"),
            "pdf_url": DAILYMED_PDF_URL.format(setid=setid),
            "label_url": DAILYMED_LABEL_URL.format(setid=setid),
        }

    async def scrape_medtech_specialties(self, max_pages: int = 2) -> Dict[str, Any]:
        url: Optional[str] = MT_PRODUCTS_URL
        visited: set[str] = set()
        all_products: Dict[str, ScrapedProduct] = {}
        rejected: List[str] = []
        pages = 0
        while url and pages < max_pages and url not in visited:
            visited.add(url)
            resp = await self._get(url)
            products, rej, next_url = parse_medtech_html(resp.text, str(resp.url))
            for p in products:
                all_products.setdefault(p.name.upper(), p)
            rejected += [r for r in rej if r not in rejected]
            pages += 1
            if next_url and urlparse(next_url).netloc != urlparse(MT_PRODUCTS_URL).netloc:
                next_url = None
            url = next_url
        return {"source": MT_PRODUCTS_URL, "pages_crawled": pages, "products": list(all_products.values()),
                "rejected_kenvue_brands": rejected}

    async def sync_all(self, max_pages: int = 2) -> Dict[str, Any]:
        """Run both portfolio scrapers concurrently, tolerating individual source failures."""
        results = await asyncio.gather(self.scrape_innovative_medicine(), self.scrape_medtech_specialties(max_pages),
                                       return_exceptions=True)
        products: List[ScrapedProduct] = []
        rejected: List[str] = []
        messages: List[str] = []
        for src, res in zip((IM_PRODUCTS_URL, MT_PRODUCTS_URL), results):
            if isinstance(res, Exception):
                messages.append(f"{src}: unavailable ({type(res).__name__}: {res})")
                continue
            products += res["products"]
            rejected += res["rejected_kenvue_brands"]
            messages.append(f"{src}: parsed {len(res['products'])} products")
        return {"products": products, "rejected_kenvue_brands": rejected, "messages": messages}
