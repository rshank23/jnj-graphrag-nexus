"""Pre-seeded Golden Dataset for the J&J post-Kenvue-spinoff portfolio.

Prices are illustrative list-price estimates used for commercial modelling only.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from app.models.schemas import EdgeType, GraphEdge, GraphNode, NodeType

IM = "J&J Innovative Medicine"
MT = "J&J MedTech"
IM_URL = "https://www.jnj.com/innovativemedicine/our-products"
MT_URL = "https://www.jnjmedtech.com/en-US/products/all-products"

KENVUE_BRANDS: Tuple[str, ...] = (
    "Tylenol",
    "Motrin",
    "Zyrtec",
    "Benadryl",
    "Listerine",
    "Neutrogena",
    "Aveeno",
    "Clean & Clear",
    "Band-Aid",
    "Neosporin",
    "Johnson's Baby",
)


def _normalize(text: str) -> str:
    text = text.lower().replace("\u2019", "'").replace("&", " and ")
    return re.sub(r"[^a-z0-9']+", " ", text).strip()


def _brand_pattern(brand: str) -> "re.Pattern[str]":
    words = [re.escape(w).replace("'", "'?") for w in _normalize(brand).split()]
    return re.compile(r"(?<![a-z0-9])" + r"\s*".join(words) + r"(?![a-z0-9])")


_KENVUE_PATTERNS = [_brand_pattern(b) for b in KENVUE_BRANDS]
_KENVUE_PATTERNS.append(re.compile(r"(?<![a-z0-9])kenvue(?![a-z0-9])"))


def is_kenvue_brand(name: str | None) -> bool:
    """Return True if the text references a spun-off Kenvue consumer-health brand."""
    if not name:
        return False
    norm = _normalize(name)
    return any(p.search(norm) for p in _KENVUE_PATTERNS)


# ---------------------------------------------------------------------------
# Node definitions
# ---------------------------------------------------------------------------

BUSINESS_UNITS: List[Dict[str, Any]] = [
    {"id": "BU_IM", "name": IM, "properties": {"description": "Pharmaceutical segment of Johnson & Johnson.", "source_url": IM_URL}},
    {"id": "BU_MT", "name": MT, "properties": {"description": "Medical technology segment of Johnson & Johnson.", "source_url": MT_URL}},
]

FRANCHISES: List[Dict[str, Any]] = [
    {"id": "FR_ONCOLOGY", "name": "Oncology", "division": IM},
    {"id": "FR_IMMUNOLOGY", "name": "Immunology", "division": IM},
    {"id": "FR_NEUROSCIENCE", "name": "Neuroscience", "division": IM},
    {"id": "FR_CARDIOPULMONARY", "name": "Cardiopulmonary / PAH", "division": IM},
    {"id": "FR_INFECTIOUS_DISEASES", "name": "Infectious Diseases", "division": IM},
    {"id": "FR_ELECTROPHYSIOLOGY", "name": "Electrophysiology", "division": MT},
    {"id": "FR_SURGERY", "name": "Surgery / Ethicon", "division": MT},
    {"id": "FR_ORTHOPAEDICS", "name": "Orthopaedics / DePuy Synthes", "division": MT},
    {"id": "FR_INTERVENTIONAL_CV", "name": "Interventional Cardiovascular", "division": MT},
    {"id": "FR_VISION", "name": "Vision", "division": MT},
]


def _mt(
    id_: str,
    name: str,
    franchise_id: str,
    category: str,
    price: float,
    sku: str,
    claim: str,
    label: NodeType = NodeType.Product,
    pricing: str = "per_procedure",
    **extra: Any,
) -> Dict[str, Any]:
    props = {
        "sku": sku,
        "category": category,
        "price_usd": price,
        "pricing_model": pricing,
        "is_capital_equipment": pricing == "capital",
        "clinical_claim": claim,
        "source_url": MT_URL,
    }
    props.update(extra)
    return {"id": id_, "label": label, "name": name, "division": MT, "franchise_id": franchise_id, "properties": props}


MEDTECH_PRODUCTS: List[Dict[str, Any]] = [
    _mt("MT_CARTO_3_V8", "CARTO 3 System V8", "FR_ELECTROPHYSIOLOGY", "Capital Platform", 285_000, "MT-EP-C3V8",
        "3D electroanatomical mapping platform providing real-time catheter visualization and magnetic/current-based localization for cardiac ablation.",
        pricing="capital", manufacturer="Biosense Webster"),
    _mt("MT_CARTOSEG_CT", "CARTOSEG CT Segmentation Module", "FR_ELECTROPHYSIOLOGY", "Software Module", 45_000, "MT-EP-CSCT",
        "Automates 3D CT segmentation of all four cardiac chambers, aorta, coronary sinus, coronary arteries, and esophagus to streamline catheter ablation planning.",
        label=NodeType.SoftwareModule, pricing="capital", modality="3D CT Segmentation", manufacturer="Biosense Webster"),
    _mt("MT_CARTOMERGE", "CARTOMERGE Image Integration Module", "FR_ELECTROPHYSIOLOGY", "Software Module", 38_000, "MT-EP-CMRG",
        "Registers pre-procedural 3D CT/MRI surface reconstructions onto the live CARTO 3 electroanatomical map.",
        label=NodeType.SoftwareModule, pricing="capital", modality="3D CT/MRI Surface Registration", manufacturer="Biosense Webster"),
    _mt("MT_CARTO_PRIME", "CARTO PRIME Mapping Module", "FR_ELECTROPHYSIOLOGY", "Software Module", 32_000, "MT-EP-CPRM",
        "Advanced coherent mapping and local activation time velocity vectors for complex arrhythmias.",
        label=NodeType.SoftwareModule, pricing="capital", manufacturer="Biosense Webster"),
    _mt("MT_CARTO_ELEVATE", "CARTO ELEVATE Module", "FR_ELECTROPHYSIOLOGY", "Software Module", 29_000, "MT-EP-CELV",
        "Multipolar and signal analysis software module for the CARTO 3 System.",
        label=NodeType.SoftwareModule, pricing="capital", manufacturer="Biosense Webster"),
    _mt("MT_CARTOREPLAY", "CARTOREPLAY Module", "FR_ELECTROPHYSIOLOGY", "Software Module", 22_000, "MT-EP-CRPL",
        "Continuous ECG and intracardiac signal recording timeline for retrospective electrogram capture.",
        label=NodeType.SoftwareModule, pricing="capital", manufacturer="Biosense Webster"),
    _mt("MT_CARTO_VIZIGO", "CARTO VIZIGO Bi-Directional Guiding Sheath", "FR_ELECTROPHYSIOLOGY", "Consumable", 1_450, "MT-EP-VZGO",
        "Direct sheath visualization on the CARTO 3 System map without fluoroscopy dependency.", manufacturer="Biosense Webster"),
    _mt("MT_ACUNAV_CRYSTAL", "AcuNav CRYSTAL Intracardiac Ultrasound Catheter", "FR_ELECTROPHYSIOLOGY", "Consumable", 3_200, "MT-EP-ACNV",
        "Real-time 2D/4D intracardiac echocardiography guiding transseptal puncture and left atrial appendage visualization.", manufacturer="Biosense Webster"),
    _mt("MT_SHOCKWAVE_IVL_GENERATOR", "Shockwave IVL Generator", "FR_INTERVENTIONAL_CV", "Capital Platform", 65_000, "MT-CV-IVLG",
        "Portable, rechargeable generator that powers Shockwave intravascular lithotripsy catheters to deliver sonic pressure waves.",
        pricing="capital", manufacturer="Shockwave Medical"),
    _mt("MT_SHOCKWAVE_JAVELIN", "Shockwave Javelin Coronary IVL Catheter", "FR_INTERVENTIONAL_CV", "Consumable", 4_800, "MT-CV-JVLN",
        "Forward-facing intravascular lithotripsy for severely calcified, difficult-to-cross coronary lesions.", manufacturer="Shockwave Medical"),
    _mt("MT_BIOPATCH_CHG", "BIOPATCH Protective Disk with CHG", "FR_SURGERY", "Consumable", 45, "MT-GS-BPCH",
        "Only sponge dressing with clinical indication to reduce Catheter-Related Bloodstream Infections (CRBSI) via 360-degree Chlorhexidine Gluconate delivery.",
        manufacturer="Ethicon"),
    _mt("MT_BLAKE_DRAIN", "BLAKE Silicone Drains & JVAC Closed Wound Drainage Reservoir", "FR_SURGERY", "Consumable", 180, "MT-GS-BLKD",
        "Four continuous open channels provide greater tissue contact area and resist clotting compared to perforated drains.", manufacturer="Ethicon"),
    _mt("MT_MONOCRYL_PLUS", "MONOCRYL Plus Antibacterial (poliglecaprone 25) Suture", "FR_SURGERY", "Consumable", 65, "MT-GS-MNCP",
        "IRGACARE MP triclosan coating inhibits bacterial colonization on the suture for 7+ days, reducing surgical site infection risk.", manufacturer="Ethicon"),
    _mt("MT_VELYS_ROBOT", "VELYS Robotic-Assisted Solution", "FR_ORTHOPAEDICS", "Capital Platform", 310_000, "MT-OR-VLYS",
        "Table-mounted high-speed optical camera and robotic saw control for sub-millimeter total knee arthroplasty resection accuracy.",
        pricing="capital", manufacturer="DePuy Synthes"),
    _mt("MT_ATTUNE_KNEE", "ATTUNE Primary Total Knee System with AOX Polyethylene", "FR_ORTHOPAEDICS", "Implant", 4_900, "MT-OR-ATTN",
        "GLIDERIGHT articulation and SOFCAM S-curve design improve kinematic stability and patient satisfaction.", manufacturer="DePuy Synthes"),
    _mt("MT_ACRION_BLADES", "ACRION Cross-Compatible Surgical Saw Blades", "FR_ORTHOPAEDICS", "Consumable", 140, "MT-OR-ACRN",
        "Engineered for precision bone resection across DePuy Synthes, Zimmer, Stryker, and ConMed Linvatec Hall power tool couplings.",
        manufacturer="DePuy Synthes"),
    _mt("MT_TECNIS_ODYSSEY", "TECNIS Odyssey IOL", "FR_VISION", "Implant", 1_200, "MT-VS-TODY",
        "Full visual range presbyopia-correcting intraocular lens for cataract surgery with high contrast and dysphotopsia tolerance.",
        manufacturer="Johnson & Johnson Vision"),
]


def _im(
    id_: str,
    name: str,
    franchise_id: str,
    mechanism: str,
    indication: str,
    generic: str,
    boxed_warning: str | None = None,
    contraindication: str | None = None,
    **extra: Any,
) -> Dict[str, Any]:
    props: Dict[str, Any] = {
        "generic_name": generic,
        "mechanism": mechanism,
        "indication": indication,
        "category": "Prescription Medicine",
        "source_url": IM_URL,
    }
    if boxed_warning:
        props["boxed_warning"] = boxed_warning
    if contraindication:
        props["contraindication"] = contraindication
    props.update(extra)
    return {"id": id_, "label": NodeType.Product, "name": name, "division": IM, "franchise_id": franchise_id, "properties": props}


PHARMA_PRODUCTS: List[Dict[str, Any]] = [
    _im("IM_CARVYKTI", "CARVYKTI (ciltacabtagene autoleucel)", "FR_ONCOLOGY", "BCMA-directed CAR-T therapy",
        "Relapsed or refractory multiple myeloma", "ciltacabtagene autoleucel",
        boxed_warning="Cytokine Release Syndrome (CRS), ICANS, Parkinsonism, Guillain-Barre syndrome, Secondary hematologic malignancies"),
    _im("IM_DARZALEX_FASPRO", "DARZALEX FASPRO (daratumumab and hyaluronidase-fihj)", "FR_ONCOLOGY",
        "Subcutaneous CD38-directed cytolytic antibody", "Multiple Myeloma & Light Chain Amyloidosis", "daratumumab and hyaluronidase-fihj"),
    _im("IM_RYBREVANT_FASPRO", "RYBREVANT FASPRO (amivantamab and hyaluronidase-lpuj)", "FR_ONCOLOGY",
        "Bispecific EGFR and MET receptor-directed antibody",
        "NSCLC with EGFR exon 19 deletions/L858R or exon 20 insertion; Recurrent/Metastatic Head and Neck Squamous Cell Carcinoma (42% ORR in 2026 trial data)",
        "amivantamab and hyaluronidase-lpuj", trial_data="42% objective response rate (ORR) in recurrent/metastatic HNSCC (2026 trial data)"),
    _im("IM_AKEEGA", "AKEEGA (niraparib and abiraterone acetate)", "FR_ONCOLOGY",
        "Dual-action PARP inhibitor + CYP17 inhibitor tablet",
        "BRCA-mutated metastatic castration-resistant prostate cancer (mCRPC)", "niraparib and abiraterone acetate"),
    _im("IM_BALVERSA", "BALVERSA (erdafitinib)", "FR_ONCOLOGY", "Pan-FGFR tyrosine kinase inhibitor",
        "Locally advanced or metastatic urothelial carcinoma with susceptible FGFR3 genetic alterations", "erdafitinib"),
    _im("IM_ERLEADA", "ERLEADA (apalutamide)", "FR_ONCOLOGY", "Androgen receptor inhibitor", "mCSPC and nmCRPC", "apalutamide"),
    _im("IM_INLEXZO", "INLEXZO (gemcitabine intravesical system)", "FR_ONCOLOGY",
        "Sustained-release intravesical nucleoside metabolic inhibitor", "Urothelial / Bladder carcinoma", "gemcitabine intravesical system"),
    _im("IM_ICOTYDE", "ICOTYDE (icotrokinra)", "FR_IMMUNOLOGY",
        "First-in-class targeted oral peptide selectively blocking the IL-23 receptor",
        "Moderate-to-severe plaque psoriasis and active psoriatic arthritis (58% ACR20 and 29% ACR50 response at Week 16 in biologic-naive patients)",
        "icotrokinra", trial_data="58% ACR20 and 29% ACR50 response at Week 16 in biologic-naive psoriatic arthritis patients"),
    _im("IM_IMAAVY", "IMAAVY (nipocalimab-aahu)", "FR_IMMUNOLOGY",
        "High-affinity fully human neonatal Fc receptor (FcRn) blocking monoclonal antibody",
        "Generalized Myasthenia Gravis (gMG) and Sjogren's disease", "nipocalimab-aahu"),
    _im("IM_TREMFYA", "TREMFYA (guselkumab)", "FR_IMMUNOLOGY", "IL-23 p19 subunit blocker",
        "Plaque Psoriasis, Psoriatic Arthritis, Ulcerative Colitis, Crohn's Disease", "guselkumab"),
    _im("IM_CAPLYTA", "CAPLYTA (lumateperone)", "FR_NEUROSCIENCE",
        "Serotonin 5-HT2A antagonist and dopamine receptor phosphoprotein modulator",
        "Schizophrenia and Bipolar I or II depression", "lumateperone",
        boxed_warning="Increased mortality in elderly patients with dementia-related psychosis; Suicidal thoughts and behaviors"),
    _im("IM_SPRAVATO", "SPRAVATO (esketamine) CIII Nasal Spray", "FR_NEUROSCIENCE", "Non-competitive NMDA receptor antagonist",
        "Treatment-resistant depression (TRD) and MDD with acute suicidal ideation", "esketamine",
        boxed_warning="Sedation, dissociation, abuse/misuse, respiratory depression; requires SPRAVATO REMS certified healthcare setting"),
    _im("IM_CONCERTA", "CONCERTA (methylphenidate HCl) Extended-Release Tablets CII", "FR_NEUROSCIENCE", "CNS stimulant",
        "Attention Deficit Hyperactivity Disorder (ADHD)", "methylphenidate HCl",
        boxed_warning="High potential for abuse and dependence"),
    _im("IM_OPSYNVI", "OPSYNVI / YUVANCI (macitentan 10mg and tadalafil 40mg)", "FR_CARDIOPULMONARY",
        "Single-tablet combination of Endothelin Receptor Antagonist (ERA) + PDE5 inhibitor",
        "Pulmonary Arterial Hypertension (PAH, WHO Group 1) WHO Functional Class II-III", "macitentan and tadalafil",
        boxed_warning="Embryo-fetal toxicity",
        contraindication="Co-administration with organic nitrates or guanylate cyclase stimulators such as riociguat; Pulmonary Veno-Occlusive Disease (PVOD)",
        pathway="Endothelin + Nitric Oxide pathways"),
    _im("IM_OPSUMIT", "OPSUMIT (macitentan)", "FR_CARDIOPULMONARY", "Endothelin receptor antagonist",
        "PAH WHO Group 1 to delay disease progression", "macitentan", pathway="Endothelin pathway"),
    _im("IM_UPTRAVI", "UPTRAVI (selexipag)", "FR_CARDIOPULMONARY", "Oral prostacyclin IP receptor agonist",
        "PAH WHO Group 1; synergistic triple-pathway combination with OPSYNVI/OPSUMIT", "selexipag", pathway="Prostacyclin pathway"),
    _im("IM_EDURANT", "EDURANT (rilpivirine)", "FR_INFECTIOUS_DISEASES",
        "Non-nucleoside reverse transcriptase inhibitor (NNRTI)", "HIV-1 infection in combination with other antiretrovirals", "rilpivirine"),
]

PROCEDURES: List[Dict[str, Any]] = [
    {"id": "PROC_AFIB_ABLATION", "name": "Catheter Ablation for Atrial Fibrillation", "division": MT, "franchise_id": "FR_ELECTROPHYSIOLOGY",
     "properties": {"specialty": "Cardiac Electrophysiology", "setting": "EP Lab", "description": "Pulmonary vein isolation guided by 3D electroanatomical mapping and intracardiac echocardiography."}},
    {"id": "PROC_TKA_ROBOTIC", "name": "Robotic-Assisted Total Knee Arthroplasty (TKA)", "division": MT, "franchise_id": "FR_ORTHOPAEDICS",
     "properties": {"specialty": "Orthopaedic Surgery", "setting": "Operating Room / ASC", "description": "Robotic-assisted bone resection and implant positioning for end-stage knee osteoarthritis."}},
    {"id": "PROC_CALCIFIED_PCI", "name": "Intravascular Lithotripsy PCI for Calcified Coronary Arteries", "division": MT, "franchise_id": "FR_INTERVENTIONAL_CV",
     "properties": {"specialty": "Interventional Cardiology", "setting": "Cath Lab", "description": "Calcium modification with coronary IVL prior to stent delivery."}},
]

ANATOMY: List[Dict[str, Any]] = [
    {"id": "ANAT_LEFT_ATRIUM", "name": "Left Atrium & Pulmonary Veins (3D CT)", "properties": {"region": "Heart"}},
    {"id": "ANAT_CORONARY_SINUS", "name": "Coronary Sinus, Aorta & Coronary Arteries (3D CT)", "properties": {"region": "Heart / Great Vessels"}},
    {"id": "ANAT_ESOPHAGUS", "name": "Esophagus (3D CT Thermal Avoidance Structure)", "properties": {"region": "Mediastinum", "note": "Critical structure for thermal injury avoidance during posterior wall ablation."}},
    {"id": "ANAT_KNEE_JOINT", "name": "Tibiofemoral & Patellofemoral Articular Surface", "properties": {"region": "Knee"}},
]

CONDITIONS: List[Dict[str, Any]] = [
    {"id": "COND_AFIB", "name": "Atrial Fibrillation", "division": MT},
    {"id": "COND_KNEE_OA", "name": "End-Stage Knee Osteoarthritis", "division": MT},
    {"id": "COND_CALCIFIED_CAD", "name": "Severely Calcified Coronary Artery Disease", "division": MT},
    {"id": "COND_CRBSI", "name": "Catheter-Related Bloodstream Infection (CRBSI)", "division": MT},
    {"id": "COND_SSI", "name": "Surgical Site Infection (SSI)", "division": MT},
    {"id": "COND_CATARACT", "name": "Cataract with Presbyopia", "division": MT},
    {"id": "COND_MULTIPLE_MYELOMA", "name": "Multiple Myeloma", "division": IM},
    {"id": "COND_AL_AMYLOIDOSIS", "name": "Light Chain (AL) Amyloidosis", "division": IM},
    {"id": "COND_NSCLC_EGFR", "name": "EGFR-Mutated Non-Small Cell Lung Cancer", "division": IM},
    {"id": "COND_HNSCC", "name": "Recurrent/Metastatic Head and Neck Squamous Cell Carcinoma", "division": IM},
    {"id": "COND_MCRPC", "name": "Metastatic Castration-Resistant Prostate Cancer", "division": IM},
    {"id": "COND_MCSPC", "name": "Metastatic Castration-Sensitive / Non-Metastatic CRPC", "division": IM},
    {"id": "COND_UROTHELIAL", "name": "Urothelial / Bladder Carcinoma", "division": IM},
    {"id": "COND_PSORIASIS", "name": "Moderate-to-Severe Plaque Psoriasis", "division": IM},
    {"id": "COND_PSA", "name": "Active Psoriatic Arthritis", "division": IM},
    {"id": "COND_IBD", "name": "Ulcerative Colitis & Crohn's Disease", "division": IM},
    {"id": "COND_GMG", "name": "Generalized Myasthenia Gravis", "division": IM},
    {"id": "COND_SJOGREN", "name": "Sjogren's Disease", "division": IM},
    {"id": "COND_SCHIZOPHRENIA", "name": "Schizophrenia", "division": IM},
    {"id": "COND_BIPOLAR_DEPRESSION", "name": "Bipolar I or II Depression", "division": IM},
    {"id": "COND_TRD", "name": "Treatment-Resistant Depression / MDD with Suicidal Ideation", "division": IM},
    {"id": "COND_ADHD", "name": "Attention Deficit Hyperactivity Disorder", "division": IM},
    {"id": "COND_PAH", "name": "Pulmonary Arterial Hypertension (WHO Group 1)", "division": IM},
    {"id": "COND_HIV1", "name": "HIV-1 Infection", "division": IM},
    {"id": "COND_NITRATE_COADMIN", "name": "Concomitant Organic Nitrate Therapy", "division": IM},
    {"id": "COND_SGC_STIMULATOR", "name": "Concomitant Guanylate Cyclase Stimulator (riociguat)", "division": IM},
    {"id": "COND_PVOD", "name": "Pulmonary Veno-Occlusive Disease (PVOD)", "division": IM},
]

EVIDENCE_DOCS: List[Dict[str, Any]] = [
    {"id": "DOC_FDA_CARVYKTI_SPL", "name": "FDA Full Prescribing Information: CARVYKTI (Updated Feb 2026)", "division": IM,
     "properties": {"doc_type": "FDA SPL", "published": "2026-02", "source_url": "https://dailymed.nlm.nih.gov/dailymed/search.cfm?query=CARVYKTI",
                    "excerpt": "BOXED WARNING: Cytokine Release Syndrome, neurologic toxicities including ICANS, Parkinsonism and Guillain-Barre syndrome, HLH/MAS, prolonged cytopenia and secondary hematologic malignancies. CARVYKTI is a BCMA-directed genetically modified autologous T cell immunotherapy indicated for relapsed or refractory multiple myeloma. Available only through a restricted REMS program."}},
    {"id": "DOC_FDA_OPSYNVI_SPL", "name": "FDA Full Prescribing Information: OPSYNVI / YUVANCI (PAH Guideline Dual-Pathway Label)", "division": IM,
     "properties": {"doc_type": "FDA SPL", "published": "2024-03", "source_url": "https://dailymed.nlm.nih.gov/dailymed/search.cfm?query=OPSYNVI",
                    "excerpt": "BOXED WARNING: Embryo-fetal toxicity; do not administer to a pregnant female. 1 INDICATIONS AND USAGE: chronic treatment of PAH (WHO Group 1) in adults of WHO Functional Class II-III. 4 CONTRAINDICATIONS: pregnancy, use of organic nitrates in any form, concomitant guanylate cyclase stimulators such as riociguat. Use is not recommended in pulmonary veno-occlusive disease (PVOD). 12.1 Mechanism of Action: macitentan is an endothelin receptor antagonist; tadalafil is a PDE5 inhibitor enhancing the nitric oxide pathway."}},
    {"id": "DOC_ACR_2026_ICOTYDE", "name": "J&J Late-Breaking Oral Presentation: ICOTYDE Phase 3 Psoriatic Arthritis & IMAAVY Sjogren's Data (2026)", "division": IM,
     "properties": {"doc_type": "Congress Presentation", "published": "2026", "source_url": "https://www.jnj.com/innovativemedicine",
                    "excerpt": "Icotrokinra, a first-in-class targeted oral peptide that selectively blocks the IL-23 receptor, achieved 58% ACR20 and 29% ACR50 response at Week 16 in biologic-naive active psoriatic arthritis patients. Nipocalimab (IMAAVY), an FcRn blocker, showed clinically meaningful improvements in Sjogren's disease activity."}},
    {"id": "DOC_RYBREVANT_HNSCC_2026", "name": "RYBREVANT FASPRO Recurrent/Metastatic HNSCC Trial Readout (2026)", "division": IM,
     "properties": {"doc_type": "Clinical Trial Readout", "published": "2026", "source_url": "https://www.jnj.com/innovativemedicine",
                    "excerpt": "Subcutaneous amivantamab (RYBREVANT FASPRO), a bispecific EGFR and MET antibody, demonstrated a 42% objective response rate in recurrent/metastatic head and neck squamous cell carcinoma, building on its approved EGFR-mutated NSCLC indications (exon 19 deletions, L858R, exon 20 insertions)."}},
    {"id": "DOC_WINDCHILL_502735931", "name": "J&J MedTech Windchill Technical Evidence Memo #502735931 & BIOPATCH CRBSI Clinical Dossier", "division": MT,
     "properties": {"doc_type": "Technical Evidence Memo", "windchill_id": "502735931", "published": "2025", "source_url": MT_URL,
                    "excerpt": "BIOPATCH Protective Disk with CHG is the only sponge dressing with a clinical indication to reduce CRBSI, delivering 360-degree chlorhexidine gluconate antimicrobial protection at the catheter insertion site. BLAKE silicone drains feature four continuous open channels. MONOCRYL Plus triclosan-coated sutures inhibit bacterial colonization for 7+ days."}},
    {"id": "DOC_CARTO3_IFU_V8", "name": "Biosense Webster CARTO 3 System V8 & CARTOSEG CT Instructions for Use", "division": MT,
     "properties": {"doc_type": "Instructions for Use", "published": "2025", "source_url": MT_URL,
                    "excerpt": "CARTO 3 System V8 supports the CARTOSEG CT Segmentation Module which automatically segments all four cardiac chambers, aorta, coronary sinus, coronary arteries and esophagus from cardiac CT. CARTOMERGE registers CT/MRI surfaces; CARTO PRIME provides coherent mapping; CARTO ELEVATE provides multipolar signal analysis; CARTOREPLAY provides continuous signal recording. VIZIGO sheaths and AcuNav CRYSTAL ICE catheters are visualized on the map."}},
    {"id": "DOC_DEPUY_VELYS_TECH", "name": "DePuy Synthes VELYS Robotic-Assisted Solution & ATTUNE Knee Surgical Technique", "division": MT,
     "properties": {"doc_type": "Surgical Technique Guide", "published": "2025", "source_url": MT_URL,
                    "excerpt": "VELYS Robotic-Assisted Solution is designed for use with the ATTUNE Total Knee System, providing table-mounted optical tracking and robotic saw control. ACRION saw blades are compatible with DePuy Synthes, Zimmer, Stryker and ConMed Linvatec Hall couplings."}},
    {"id": "DOC_SHOCKWAVE_JAVELIN_IFU", "name": "Shockwave Javelin Coronary IVL Catheter Instructions for Use", "division": MT,
     "properties": {"doc_type": "Instructions for Use", "published": "2025", "source_url": MT_URL,
                    "excerpt": "The Shockwave Javelin coronary IVL catheter delivers forward-facing lithotripsy energy from the Shockwave IVL Generator to modify severely calcified, difficult-to-cross coronary lesions prior to stenting."}},
]

COUPLINGS: List[Dict[str, Any]] = [
    {"id": "COUPLING_DEPUY", "name": "DePuy Synthes Power Tool Coupling"},
    {"id": "COUPLING_ZIMMER", "name": "Zimmer Power Tool Coupling"},
    {"id": "COUPLING_STRYKER", "name": "Stryker Power Tool Coupling"},
    {"id": "COUPLING_CONMED_HALL", "name": "ConMed Linvatec Hall Power Tool Coupling"},
]

# ---------------------------------------------------------------------------
# Edge definitions
# ---------------------------------------------------------------------------

E = EdgeType
EDGE_SPECS: List[Tuple[str, str, EdgeType, Dict[str, Any]]] = [
    # --- Atrial fibrillation ablation ecosystem
    ("MT_CARTO_3_V8", "PROC_AFIB_ABLATION", E.PRIMARY_PLATFORM_FOR, {"tier": 1}),
    ("MT_CARTOSEG_CT", "MT_CARTO_3_V8", E.INTEGRATES_WITH, {"tier": 2}),
    ("MT_CARTOMERGE", "MT_CARTO_3_V8", E.INTEGRATES_WITH, {"tier": 2}),
    ("MT_CARTO_PRIME", "MT_CARTO_3_V8", E.INTEGRATES_WITH, {"tier": 2}),
    ("MT_CARTO_ELEVATE", "MT_CARTO_3_V8", E.INTEGRATES_WITH, {"tier": 2}),
    ("MT_CARTOREPLAY", "MT_CARTO_3_V8", E.INTEGRATES_WITH, {"tier": 2}),
    ("MT_CARTOSEG_CT", "ANAT_LEFT_ATRIUM", E.AUTO_SEGMENTS_3D_CT, {}),
    ("MT_CARTOSEG_CT", "ANAT_CORONARY_SINUS", E.AUTO_SEGMENTS_3D_CT, {}),
    ("MT_CARTOSEG_CT", "ANAT_ESOPHAGUS", E.AUTO_SEGMENTS_3D_CT, {}),
    ("MT_CARTOMERGE", "ANAT_LEFT_ATRIUM", E.AUTO_SEGMENTS_3D_CT, {"modality": "CT/MRI registration"}),
    ("MT_CARTO_VIZIGO", "MT_CARTO_3_V8", E.COMPATIBLE_ACCESSORY, {"tier": 3}),
    ("MT_ACUNAV_CRYSTAL", "MT_CARTO_3_V8", E.COMPATIBLE_ACCESSORY, {"tier": 3}),
    ("MT_ACUNAV_CRYSTAL", "PROC_AFIB_ABLATION", E.GUIDES_TRANSSEPTAL_PUNCTURE, {"tier": 3}),
    ("MT_BIOPATCH_CHG", "PROC_AFIB_ABLATION", E.POST_OP_INFECTION_CONTROL_FOR, {"tier": 4, "site": "Femoral venous access / central line"}),
    ("PROC_AFIB_ABLATION", "COND_AFIB", E.INDICATED_FOR, {}),
    ("PROC_AFIB_ABLATION", "ANAT_LEFT_ATRIUM", E.INDICATED_FOR, {"target": "Pulmonary vein isolation"}),
    # --- Robotic TKA ecosystem
    ("MT_VELYS_ROBOT", "PROC_TKA_ROBOTIC", E.PRIMARY_PLATFORM_FOR, {"tier": 1}),
    ("MT_ATTUNE_KNEE", "MT_VELYS_ROBOT", E.COMPATIBLE_ACCESSORY, {"tier": 3}),
    ("MT_ATTUNE_KNEE", "PROC_TKA_ROBOTIC", E.INDICATED_FOR, {"tier": 3}),
    ("MT_ACRION_BLADES", "MT_VELYS_ROBOT", E.COMPATIBLE_ACCESSORY, {"tier": 3}),
    ("MT_ACRION_BLADES", "COUPLING_DEPUY", E.COMPATIBLE_COUPLING, {}),
    ("MT_ACRION_BLADES", "COUPLING_ZIMMER", E.COMPATIBLE_COUPLING, {}),
    ("MT_ACRION_BLADES", "COUPLING_STRYKER", E.COMPATIBLE_COUPLING, {}),
    ("MT_ACRION_BLADES", "COUPLING_CONMED_HALL", E.COMPATIBLE_COUPLING, {}),
    ("MT_BLAKE_DRAIN", "PROC_TKA_ROBOTIC", E.POST_OP_DRAINAGE_FOR, {"tier": 4}),
    ("MT_MONOCRYL_PLUS", "PROC_TKA_ROBOTIC", E.POST_OP_INFECTION_CONTROL_FOR, {"tier": 4}),
    ("PROC_TKA_ROBOTIC", "ANAT_KNEE_JOINT", E.INDICATED_FOR, {}),
    ("PROC_TKA_ROBOTIC", "COND_KNEE_OA", E.INDICATED_FOR, {}),
    # --- Calcified PCI ecosystem
    ("MT_SHOCKWAVE_IVL_GENERATOR", "PROC_CALCIFIED_PCI", E.PRIMARY_PLATFORM_FOR, {"tier": 1}),
    ("MT_SHOCKWAVE_JAVELIN", "MT_SHOCKWAVE_IVL_GENERATOR", E.COMPATIBLE_ACCESSORY, {"tier": 3}),
    ("MT_SHOCKWAVE_JAVELIN", "PROC_CALCIFIED_PCI", E.INDICATED_FOR, {"tier": 3}),
    ("MT_BIOPATCH_CHG", "PROC_CALCIFIED_PCI", E.POST_OP_INFECTION_CONTROL_FOR, {"tier": 4, "site": "Arterial access site"}),
    ("PROC_CALCIFIED_PCI", "COND_CALCIFIED_CAD", E.INDICATED_FOR, {}),
    ("PROC_CALCIFIED_PCI", "ANAT_CORONARY_SINUS", E.INDICATED_FOR, {"target": "Coronary arteries"}),
    # --- Infection control & vision
    ("MT_BIOPATCH_CHG", "COND_CRBSI", E.INDICATED_FOR, {}),
    ("MT_MONOCRYL_PLUS", "COND_SSI", E.INDICATED_FOR, {}),
    ("MT_BLAKE_DRAIN", "COND_SSI", E.INDICATED_FOR, {"role": "Closed wound drainage reduces seroma/hematoma"}),
    ("MT_TECNIS_ODYSSEY", "COND_CATARACT", E.INDICATED_FOR, {}),
    # --- MedTech evidence
    ("MT_CARTO_3_V8", "DOC_CARTO3_IFU_V8", E.SUPPORTED_BY_EVIDENCE, {}),
    ("MT_CARTOSEG_CT", "DOC_CARTO3_IFU_V8", E.SUPPORTED_BY_EVIDENCE, {}),
    ("MT_CARTOMERGE", "DOC_CARTO3_IFU_V8", E.SUPPORTED_BY_EVIDENCE, {}),
    ("MT_CARTO_PRIME", "DOC_CARTO3_IFU_V8", E.SUPPORTED_BY_EVIDENCE, {}),
    ("MT_CARTO_ELEVATE", "DOC_CARTO3_IFU_V8", E.SUPPORTED_BY_EVIDENCE, {}),
    ("MT_CARTOREPLAY", "DOC_CARTO3_IFU_V8", E.SUPPORTED_BY_EVIDENCE, {}),
    ("MT_CARTO_VIZIGO", "DOC_CARTO3_IFU_V8", E.SUPPORTED_BY_EVIDENCE, {}),
    ("MT_ACUNAV_CRYSTAL", "DOC_CARTO3_IFU_V8", E.SUPPORTED_BY_EVIDENCE, {}),
    ("MT_BIOPATCH_CHG", "DOC_WINDCHILL_502735931", E.SUPPORTED_BY_EVIDENCE, {}),
    ("MT_BLAKE_DRAIN", "DOC_WINDCHILL_502735931", E.SUPPORTED_BY_EVIDENCE, {}),
    ("MT_MONOCRYL_PLUS", "DOC_WINDCHILL_502735931", E.SUPPORTED_BY_EVIDENCE, {}),
    ("MT_VELYS_ROBOT", "DOC_DEPUY_VELYS_TECH", E.SUPPORTED_BY_EVIDENCE, {}),
    ("MT_ATTUNE_KNEE", "DOC_DEPUY_VELYS_TECH", E.SUPPORTED_BY_EVIDENCE, {}),
    ("MT_ACRION_BLADES", "DOC_DEPUY_VELYS_TECH", E.SUPPORTED_BY_EVIDENCE, {}),
    ("MT_SHOCKWAVE_JAVELIN", "DOC_SHOCKWAVE_JAVELIN_IFU", E.SUPPORTED_BY_EVIDENCE, {}),
    ("MT_SHOCKWAVE_IVL_GENERATOR", "DOC_SHOCKWAVE_JAVELIN_IFU", E.SUPPORTED_BY_EVIDENCE, {}),
    # --- Oncology
    ("IM_CARVYKTI", "COND_MULTIPLE_MYELOMA", E.INDICATED_FOR, {"line": "Relapsed or refractory"}),
    ("IM_DARZALEX_FASPRO", "COND_MULTIPLE_MYELOMA", E.INDICATED_FOR, {}),
    ("IM_DARZALEX_FASPRO", "COND_AL_AMYLOIDOSIS", E.INDICATED_FOR, {}),
    ("IM_RYBREVANT_FASPRO", "COND_NSCLC_EGFR", E.INDICATED_FOR, {}),
    ("IM_RYBREVANT_FASPRO", "COND_HNSCC", E.INDICATED_FOR, {"evidence": "42% ORR (2026 trial data)"}),
    ("IM_AKEEGA", "COND_MCRPC", E.INDICATED_FOR, {"biomarker": "BRCA-mutated"}),
    ("IM_ERLEADA", "COND_MCSPC", E.INDICATED_FOR, {}),
    ("IM_BALVERSA", "COND_UROTHELIAL", E.INDICATED_FOR, {"biomarker": "FGFR3 alterations"}),
    ("IM_INLEXZO", "COND_UROTHELIAL", E.INDICATED_FOR, {}),
    ("IM_CARVYKTI", "IM_DARZALEX_FASPRO", E.SYNERGISTIC_PATHWAY_WITH, {"rationale": "Sequential BCMA and CD38 targeting across multiple myeloma lines of therapy"}),
    ("IM_AKEEGA", "IM_ERLEADA", E.SYNERGISTIC_PATHWAY_WITH, {"rationale": "Androgen-axis portfolio across prostate cancer disease states"}),
    ("IM_CARVYKTI", "DOC_FDA_CARVYKTI_SPL", E.SUPPORTED_BY_EVIDENCE, {}),
    ("IM_RYBREVANT_FASPRO", "DOC_RYBREVANT_HNSCC_2026", E.SUPPORTED_BY_EVIDENCE, {}),
    # --- Immunology
    ("IM_ICOTYDE", "COND_PSORIASIS", E.INDICATED_FOR, {}),
    ("IM_ICOTYDE", "COND_PSA", E.INDICATED_FOR, {"evidence": "58% ACR20 / 29% ACR50 at Week 16"}),
    ("IM_TREMFYA", "COND_PSORIASIS", E.INDICATED_FOR, {}),
    ("IM_TREMFYA", "COND_PSA", E.INDICATED_FOR, {}),
    ("IM_TREMFYA", "COND_IBD", E.INDICATED_FOR, {}),
    ("IM_IMAAVY", "COND_GMG", E.INDICATED_FOR, {}),
    ("IM_IMAAVY", "COND_SJOGREN", E.INDICATED_FOR, {}),
    ("IM_ICOTYDE", "IM_TREMFYA", E.SYNERGISTIC_PATHWAY_WITH, {"rationale": "Oral IL-23 receptor blockade complements injectable IL-23 p19 blockade within the IL-23 pathway franchise"}),
    ("IM_ICOTYDE", "DOC_ACR_2026_ICOTYDE", E.SUPPORTED_BY_EVIDENCE, {}),
    ("IM_IMAAVY", "DOC_ACR_2026_ICOTYDE", E.SUPPORTED_BY_EVIDENCE, {}),
    # --- Neuroscience
    ("IM_CAPLYTA", "COND_SCHIZOPHRENIA", E.INDICATED_FOR, {}),
    ("IM_CAPLYTA", "COND_BIPOLAR_DEPRESSION", E.INDICATED_FOR, {}),
    ("IM_SPRAVATO", "COND_TRD", E.INDICATED_FOR, {}),
    ("IM_CONCERTA", "COND_ADHD", E.INDICATED_FOR, {}),
    # --- Cardiopulmonary / PAH
    ("IM_OPSYNVI", "COND_PAH", E.INDICATED_FOR, {"functional_class": "WHO FC II-III"}),
    ("IM_OPSUMIT", "COND_PAH", E.INDICATED_FOR, {}),
    ("IM_UPTRAVI", "COND_PAH", E.INDICATED_FOR, {}),
    ("IM_OPSYNVI", "IM_UPTRAVI", E.SYNERGISTIC_PATHWAY_WITH, {"rationale": "Endothelin + nitric oxide (OPSYNVI) plus prostacyclin (UPTRAVI) = triple-pathway PAH therapy"}),
    ("IM_OPSUMIT", "IM_UPTRAVI", E.SYNERGISTIC_PATHWAY_WITH, {"rationale": "Endothelin + prostacyclin pathway combination"}),
    ("IM_OPSUMIT", "IM_OPSYNVI", E.SYNERGISTIC_PATHWAY_WITH, {"rationale": "OPSYNVI contains macitentan 10 mg; patients may transition from OPSUMIT monotherapy to single-tablet dual therapy"}),
    ("IM_OPSYNVI", "COND_NITRATE_COADMIN", E.CONTRAINDICATED_WITH, {"severity": "Contraindicated"}),
    ("IM_OPSYNVI", "COND_SGC_STIMULATOR", E.CONTRAINDICATED_WITH, {"severity": "Contraindicated"}),
    ("IM_OPSYNVI", "COND_PVOD", E.CONTRAINDICATED_WITH, {"severity": "Not recommended"}),
    ("IM_OPSYNVI", "DOC_FDA_OPSYNVI_SPL", E.SUPPORTED_BY_EVIDENCE, {}),
    ("IM_OPSUMIT", "DOC_FDA_OPSYNVI_SPL", E.SUPPORTED_BY_EVIDENCE, {}),
    ("IM_UPTRAVI", "DOC_FDA_OPSYNVI_SPL", E.SUPPORTED_BY_EVIDENCE, {}),
    # --- Infectious disease
    ("IM_EDURANT", "COND_HIV1", E.INDICATED_FOR, {}),
]


def _boxed_warning_nodes() -> List[Dict[str, Any]]:
    out = []
    for p in PHARMA_PRODUCTS:
        bw = p["properties"].get("boxed_warning")
        if bw:
            out.append({
                "id": f"BW_{p['id'][3:]}",
                "name": f"Boxed Warning: {p['name'].split(' (')[0].split(' /')[0]}",
                "division": IM,
                "product_id": p["id"],
                "properties": {"warning_text": bw},
            })
    return out


BOXED_WARNINGS = _boxed_warning_nodes()

BOXED_WARNING_EVIDENCE = {
    "BW_CARVYKTI": "DOC_FDA_CARVYKTI_SPL",
    "BW_OPSYNVI": "DOC_FDA_OPSYNVI_SPL",
}


def build_seed_graph() -> Tuple[List[GraphNode], List[GraphEdge]]:
    """Materialize the full golden dataset as validated GraphNode / GraphEdge objects."""
    nodes: List[GraphNode] = []
    edges: List[GraphEdge] = []
    franchise_names = {f["id"]: f["name"] for f in FRANCHISES}

    for bu in BUSINESS_UNITS:
        nodes.append(GraphNode(id=bu["id"], label=NodeType.BusinessUnit, name=bu["name"], division=bu["name"], properties=bu["properties"]))

    for fr in FRANCHISES:
        nodes.append(GraphNode(id=fr["id"], label=NodeType.Franchise, name=fr["name"], division=fr["division"], franchise=fr["name"]))
        edges.append(GraphEdge(source=fr["id"], target="BU_IM" if fr["division"] == IM else "BU_MT", relation=EdgeType.BELONGS_TO_UNIT))

    for p in MEDTECH_PRODUCTS + PHARMA_PRODUCTS:
        nodes.append(GraphNode(id=p["id"], label=p["label"], name=p["name"], division=p["division"],
                               franchise=franchise_names[p["franchise_id"]], properties=dict(p["properties"])))
        edges.append(GraphEdge(source=p["id"], target=p["franchise_id"], relation=EdgeType.IN_FRANCHISE))

    for proc in PROCEDURES:
        nodes.append(GraphNode(id=proc["id"], label=NodeType.Procedure, name=proc["name"], division=proc["division"],
                               franchise=franchise_names[proc["franchise_id"]], properties=proc["properties"]))

    for a in ANATOMY:
        nodes.append(GraphNode(id=a["id"], label=NodeType.Anatomy, name=a["name"], division=MT, properties=a["properties"]))

    for c in CONDITIONS:
        nodes.append(GraphNode(id=c["id"], label=NodeType.ClinicalCondition, name=c["name"], division=c["division"]))

    for d in EVIDENCE_DOCS:
        nodes.append(GraphNode(id=d["id"], label=NodeType.EvidenceDocument, name=d["name"], division=d["division"], properties=d["properties"]))

    for c in COUPLINGS:
        nodes.append(GraphNode(id=c["id"], label=NodeType.HardwareCoupling, name=c["name"], division=MT, franchise="Orthopaedics / DePuy Synthes"))

    for bw in BOXED_WARNINGS:
        nodes.append(GraphNode(id=bw["id"], label=NodeType.BoxedWarning, name=bw["name"], division=IM, properties=bw["properties"]))
        edges.append(GraphEdge(source=bw["product_id"], target=bw["id"], relation=EdgeType.HAS_BOXED_WARNING))
        doc = BOXED_WARNING_EVIDENCE.get(bw["id"])
        if doc:
            edges.append(GraphEdge(source=bw["id"], target=doc, relation=EdgeType.SUPPORTED_BY_EVIDENCE))

    for src, tgt, rel, props in EDGE_SPECS:
        edges.append(GraphEdge(source=src, target=tgt, relation=rel, properties=dict(props)))

    return nodes, edges
