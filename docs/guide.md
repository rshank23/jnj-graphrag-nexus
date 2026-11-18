# GraphRAG Nexus: a beginner's guide (for the presenter)

This guide is for you, the presenter, if you are new to J&J and the healthcare business. Read it top to bottom once. After that, use it as a reference before each meeting.

It explains:

1. How J&J's business works (who buys, who sells, what the rules are)
2. Every piece of jargon used in the decks, in plain English
3. The problem we are solving
4. How Nexus works and how the code handles each point
5. The value deck (`JnJ-GraphRAG-Nexus-Value-B2B.pptx`), slide by slide, with what to say
6. "Why not just use a chatbot?", explained simply
7. Questions you will likely be asked, with answers
8. What is real today and what is still an estimate (so you never overclaim)
9. A live demo script

> **Golden rule:** never claim more than this guide says is proven. Where something is an estimate or illustrative, say so. Being honest is what makes a client trust a POC.

---

## Part 1: How J&J's business works

### 1.1 What J&J sells

Johnson & Johnson (J&J) today has **two businesses**:

| Business | What it makes | Examples in our app |
|---|---|---|
| **Innovative Medicine** (formerly Janssen, the pharma side) | Prescription medicines | **TREMFYA** (immunology: psoriasis, psoriatic arthritis, ulcerative colitis, Crohn's disease), **CARVYKTI** (a cell therapy for multiple myeloma, a blood cancer), DARZALEX, ERLEADA |
| **MedTech** (medical devices) | Equipment and supplies used in hospitals and surgery | **CARTO 3** (heart-mapping system), **VIZIGO** and **AcuNav** (catheters used inside the heart), **BIOPATCH** (an antiseptic dressing), knee implants, sutures, eye lenses |

J&J **used to** also sell consumer products (Tylenol, Neutrogena, Band-Aid, Listerine). That business was separated in 2023 into a different company called **Kenvue**. Kenvue products are **not J&J products any more**, so our app deliberately rejects them (see the "Kenvue guard" in Part 4).

### 1.2 Franchises: why J&J is "siloed"

Inside each business, products are grouped into **franchises**, which are business units focused on one medical area. Examples:

- **Electrophysiology (EP):** heart-rhythm products such as CARTO, VIZIGO and AcuNav (the brand is Biosense Webster)
- **Surgery:** surgical products such as BIOPATCH and sutures (the brand is Ethicon)
- **Oncology:** cancer medicines such as CARVYKTI and DARZALEX
- **Immunology:** medicines such as TREMFYA

Each franchise usually has its **own sales team, own documents, own systems and own targets**. This is called being **siloed**. It is normal in big companies, but it means nobody easily sees the links *between* franchises. Remember this, because it is the root of the "cross-selling" problem.

### 1.3 B2B: J&J sells to organisations, not to consumers

**B2B (business-to-business)** means J&J sells to organisations, not to individual shoppers. Patients do not buy CARTO 3 or CARVYKTI at a shop. Hospitals, health systems and insurers decide what gets bought and used.

These are the **customers**, and the jargon you will hear for each:

| Customer | What it is | What it decides |
|---|---|---|
| **Hospital** | A single hospital | What to buy and use |
| **IDN (Integrated Delivery Network)** | A group of hospitals and clinics owned or run as one system | Buys centrally for all its hospitals, so it is a big customer |
| **GPO (Group Purchasing Organisation)** | A buying club that negotiates prices for many hospitals together | Negotiates contracts and prices |
| **VAC (Value Analysis Committee)** | A committee *inside* a hospital (doctors, nurses, finance, supply chain) | Approves new devices. It wants evidence that a product is clinically good and worth the money |
| **P&T Committee (Pharmacy & Therapeutics)** | A hospital committee of doctors and pharmacists | Decides which medicines go on the **formulary** (the hospital's list of approved drugs) |
| **Payer** | Insurance companies, government programmes, PBMs (pharmacy benefit managers) | Whether they will **pay for** a medicine, and under what conditions |
| **HCP (Healthcare Professional)** | Doctors, nurses, pharmacists | Which product to use for a patient |
| **KOL (Key Opinion Leader)** | A well-known, respected doctor in a field | Influences other doctors |
| **Biomed / supply chain** | The hospital teams that maintain equipment and manage stock | Act on recalls and order the right parts |

**Why B2B matters for our pitch:** in B2B, the customer's experience is about **speed, accuracy and trust**:

- How fast can J&J give a correct, complete, evidence-backed answer or quote?
- How safely does J&J handle a recall?

The cost to J&J is mostly **people's time**: reps, medical staff and reviewers searching documents and going back and forth. That is exactly what Nexus reduces.

### 1.4 Who works at J&J on these deals (the internal roles)

| Role | What they do | Important rule |
|---|---|---|
| **Sales rep / Commercial** | Sells products to hospitals and doctors | **Can only talk about approved uses** ("on-label"). See Compliance below. |
| **KAM (Key Account Manager)** | A senior rep who manages a big customer, such as an IDN, across many products | Same rules as Commercial |
| **Medical Affairs** | The scientific team: doctors and pharmacists employed by J&J | Can answer scientific questions, including about unapproved uses, but only when an HCP asks first ("unsolicited request") |
| **MSL (Medical Science Liaison)** | A field-based Medical Affairs scientist who talks to doctors and KOLs | Scientific, not sales |
| **Medical Information** | The team that answers incoming questions from doctors and hospitals | Gives written, referenced answers |
| **Marketing** | Creates promotional material: brochures, slide decks, emails, websites | Everything must pass **MLR review** before use |
| **MLR reviewers** | Medical, Legal and Regulatory experts who approve or reject marketing material | They are the compliance gatekeepers |

The separation between **Commercial (sales)** and **Medical** is sometimes called the **firewall**. Sales must not drift into unapproved science. Medical must not become a sales channel.

---

## Part 2: The jargon, explained

### 2.1 Compliance (the most important concept)

**Compliance** means **following the laws and rules about how a company may talk about and sell its products**. In healthcare these rules are very strict because wrong information can harm patients.

In the US, the regulator is the **FDA (Food and Drug Administration)**. It approves every medicine and device *for specific uses*, and it controls what companies may say in promotion.

The key compliance ideas:

| Term | Plain meaning | Example |
|---|---|---|
| **Label / Prescribing Information (PI)** | The official FDA-approved document for a medicine. It says what the medicine is approved for, its dose, its risks, etc. Legally, this is "the truth" the company must stick to. | TREMFYA's label lists psoriasis, psoriatic arthritis, ulcerative colitis and Crohn's disease |
| **IFU (Instructions for Use)** | The device equivalent of a label | The CARTO 3 IFU |
| **Indication** | A disease or use the product is **approved** for | CARVYKTI is indicated for relapsed/refractory multiple myeloma |
| **On-label** | Talking about an approved indication | "TREMFYA for psoriasis" |
| **Off-label** | Talking about a use that is **not** approved | "TREMFYA for multiple myeloma" is off-label |
| **Off-label promotion** | A sales or marketing person promoting an unapproved use. **This is illegal** and has led to very large fines across the pharma industry. | A rep telling a doctor "you could also try TREMFYA for myeloma" |
| **Contraindication** | A situation where the product **must not** be used | e.g. a known serious allergy to the product |
| **Boxed warning ("black box")** | The FDA's strongest warning, printed in a box at the top of the label | CARVYKTI has one for cytokine release syndrome, neurologic toxicities and more |
| **REMS (Risk Evaluation and Mitigation Strategy)** | An FDA-required safety programme. Only certified hospitals or doctors may use the product. | CARVYKTI is only available through a REMS programme |
| **Fair balance** | Promotional material must show the **risks** as clearly as the **benefits** | A brochure that only lists benefits fails fair balance |
| **Comparative / superiority claim** | Saying "better than", "best" or "#1". This needs head-to-head trial evidence. | "TREMFYA is superior to X" needs proof |
| **Absolute claim** | Overstated wording like "cures", "no side effects" or "100% safe". Almost never allowed. | "TREMFYA cures psoriasis" is not allowed |
| **Adverse event (AE)** | Any harmful event in a patient using the product | A side effect reported to the FDA |
| **Safety signal** | A pattern in adverse-event reports suggesting a possible new risk | More reports of X than expected |
| **Recall** | The product is pulled back or corrected because of a problem. **Class I** is the most serious (could cause serious harm or death), then Class II, then Class III. | A batch of catheters is recalled |
| **Label change** | The FDA approves an update to the label, e.g. a new warning or a new indication | When a warning is added, all marketing material that mentions the product must be re-checked |
| **21 CFR 202.1** | The US federal regulation on prescription-drug advertising. Our MLR tool cites it as the rule behind a finding. | "This claim may breach 21 CFR 202.1(e)(6)(i)" |

**Why J&J cares so much:** a single compliance failure can mean regulatory action, fines, lawsuits and reputational damage, and above all it can harm patients. So companies spend heavily on review processes and training.

### 2.2 MLR review

**MLR = Medical, Legal, Regulatory review.** Before any promotional material reaches a customer (a brochure, a payer slide deck, an email, a website), three experts check it:

- **Medical:** is it scientifically accurate and supported by evidence?
- **Legal:** could it expose J&J to legal risk?
- **Regulatory:** does it follow FDA rules (on-label, fair balance, no absolute claims)?

**The problem with MLR today:**

- It is slow. In the industry it is commonly weeks per piece of material, often with several rounds of "fix this, resubmit".
- Most rejections are for **repeatable, predictable mistakes**: "cures", missing risk information, off-label mentions, claims of compatibility that are not documented.
- Reviewers are expensive experts who spend time catching basic errors.

**What we do:** an **MLR Pre-Review**. Before a draft is submitted, the app checks it automatically and points out the likely problems, with a suggested rewrite. Humans still do the real MLR review; we just make the draft much cleaner when it arrives. (Details in Part 4.)

### 2.3 Cross-selling, bundles and procedures

**Cross-selling** means **selling additional, related products to a customer who is already buying one product from you**. Simple example: a phone shop sells you a phone and then also a case and a charger.

**In J&J MedTech**, the natural unit is a **procedure**: an operation or medical intervention. One procedure uses products from **several franchises**.

Take an **AFib ablation** procedure (*AFib = atrial fibrillation*, an irregular heartbeat; *ablation* = the doctor threads a catheter into the heart and destroys the small area causing the bad rhythm). It uses:

| Product | Franchise | Type | What it does in the procedure | Illustrative price in the app |
|---|---|---|---|---|
| CARTO 3 System V8 | EP | **Capital equipment** (bought once) | Builds a 3D map of the heart | $285,000 |
| 5 CARTO software modules (CARTOSEG, CARTOMERGE, CARTO PRIME, CARTO ELEVATE, CARTOREPLAY) | EP | **Software modules** (bought once) | Add imaging and mapping features | $166,000 total |
| CARTO VIZIGO sheath | EP | **Consumable** (used once per patient) | Guides the catheter | $1,450 per case |
| AcuNav CRYSTAL catheter | EP | Consumable | Ultrasound from inside the heart | $3,200 per case |
| BIOPATCH | **Surgery (Ethicon)**, a different franchise | Consumable | Antiseptic dressing at the catheter entry site to reduce infection | $45 per case |

Some business terms that come with this:

- **Capital equipment:** big, expensive, bought once (machines, systems).
- **Consumables / disposables:** used once per patient and bought again and again. This is the **recurring revenue**.
- **Bundle:** selling the whole set of products a procedure needs, together.
- **Attach rate:** how often a second product is sold together with the first. A higher attach rate means more cross-selling.
- **Deal value / revenue per account:** the total value of what one customer buys.

**The cross-selling problem:** the EP rep sells CARTO, but BIOPATCH belongs to a different franchise and a different team. No document says "CARTO and BIOPATCH go together". The link only exists because **both are used in the same procedure**. So the opportunity is often missed.

**The numbers our app computes** (illustrative prices, 500 procedures a year):

- Capital: $285,000 + $166,000 = **$451,000** (one time)
- Consumables per case: $1,450 + $3,200 + $45 = **$4,695**
- Consumables per year: $4,695 × 500 = **$2,347,500**
- Total first-year deal value: $451,000 + $2,347,500 = **$2,798,500 (about $2.8M)**

The consumables are worth far more than the capital sale over time. That is the business case for selling the whole procedure.

> Prices are **illustrative list prices in the POC**, not real J&J contract prices. Always say "illustrative".

### 2.4 The technology terms

| Term | Plain meaning |
|---|---|
| **LLM (Large Language Model)** | The AI engine behind ChatGPT, Copilot, etc. It is very good at writing fluent text and **does not know what is true**. It predicts likely words. |
| **Chatbot** | An app where you type a question and an LLM answers. |
| **Hallucination** | When an LLM confidently makes something up, e.g. invents a price, a study or an approved use. |
| **RAG (Retrieval-Augmented Generation)** | The common way to make a chatbot use *your* documents: (1) search your documents for relevant passages, (2) give those passages to the LLM, (3) the LLM writes an answer from them. Most company chatbots work this way. |
| **Chunk** | Documents are cut into small pieces (chunks, usually a paragraph or so) so they can be searched. |
| **Vector search / embeddings** | A way of finding chunks whose *meaning* is similar to the question, not just matching words. This is the "search" in most chatbots. |
| **Top-k** | The chatbot only takes the best *k* chunks (say 5 or 10) and ignores the rest. If the answer needs the 11th chunk, it is missed. |
| **BM25 / keyword search** | Classic search that matches words, like a basic search engine. |
| **Hybrid search** | Keyword search and vector search combined. |
| **Knowledge graph** | A database that stores **things** and the **relationships between them**, like a map of connections. (Detailed in Part 3.) |
| **Node** | A "thing" in the graph: a product, a procedure, a disease, a document, a recall. |
| **Edge** | A relationship between two nodes, with a type, e.g. `CARTO 3 —PRIMARY_PLATFORM_FOR→ AFib ablation`. |
| **Traversal / multi-hop** | Following edges from node to node. "One hop" = one relationship; "multi-hop" = a chain. |
| **GraphRAG** | RAG where the search uses the knowledge graph (following relationships) as well as text search. That is our approach. |
| **Citation** | The source document an answer came from, so a human can check it. |
| **Deterministic** | The same input always gives the same result. Rules and graph queries are deterministic; LLMs are not. |
| **Role-based access** | What you can see or do depends on your role (commercial, medical, MLR, admin). |
| **Audit log / hash chain** | A record of every question and answer. "Hash-chained" means each entry contains a fingerprint of the previous one, so if anyone edits or deletes an old entry, the chain breaks and the tampering can be detected. |
| **MCP (Model Context Protocol)** | A standard "plug" that lets AI assistants (Copilot, Claude, ChatGPT-style tools) call external tools. Our app exposes its features over MCP, so any chatbot can use them. |
| **API** | A way for one program to call another. |
| **POC (Proof of Concept)** | A working prototype to prove an idea, not a finished production system. |

### 2.5 The evaluation numbers (how we prove search quality)

We built a **golden set**: 40 test questions where we know the correct answer document. We ran each search method on them and measured:

- **MRR (Mean Reciprocal Rank):** "How high up the list is the correct document?"
  - If the right document is ranked **1st**, the score is 1.0. If 2nd, 0.5. If 3rd, 0.33. If 4th, 0.25. We then average over all questions.
  - **1.0 = perfect, always first.**

| Method | MRR | Plain meaning |
|---|---|---|
| Vector search (what a typical chatbot uses) | **0.570** | The right document is often not first; on average around 2nd place |
| Hybrid search | 0.645 | A bit better |
| Keyword search (BM25) | 0.678 | A bit better again |
| **GraphRAG (ours)** | **0.975** | The right document is almost always first |

The other measures in [EVAL.md](EVAL.md):

| Measure | Score | Plain meaning |
|---|---|---|
| **Recall@5** | 0.988 | The right document is in the top 5 almost every time |
| **Routing accuracy** | 0.975 | The question goes to the right specialist agent |
| **Groundedness** | 1.0 | Answers are based on retrieved evidence |
| **Citation precision** | 0.745 | About three quarters of citations point to the exact expected source |

> These are measured on **our POC data and our 40 questions**, not on J&J production data. Say: "On our test set…".

---

## Part 3: The problem, and the idea behind Nexus

### 3.1 The problem in one paragraph

J&J's knowledge is spread across thousands of documents (labels, IFUs, trial results, safety reports, price lists, marketing material) owned by separate franchises. People answer customer questions by **manually searching** these documents. That is slow and expensive, and there are three specific risks:

- **Compliance risk:** someone says something off-label.
- **Missed revenue:** nobody sees the cross-franchise links.
- **Out-of-date answers:** a label changed and material was not updated.

### 3.2 What a knowledge graph is, by example

Think of it as a **map of connections**. Here is a small, real piece of our graph:

```
                     PRIMARY_PLATFORM_FOR
  [CARTO 3 V8] ─────────────────────────────► [AFib ablation] ──INDICATED_FOR──► [Atrial fibrillation]
   (EP franchise)                                ▲       ▲
                                                 │       │ POST_OP_INFECTION_CONTROL_FOR
             GUIDES_TRANSSEPTAL_PUNCTURE         │       │
  [AcuNav CRYSTAL] ──────────────────────────────┘    [BIOPATCH]
                                                       (Surgery / Ethicon franchise)

  [TREMFYA] ──INDICATED_FOR──► [Plaque psoriasis], [Psoriatic arthritis], [Inflammatory bowel disease*]
            (no edge to Multiple myeloma)

  * Inflammatory bowel disease (IBD) covers ulcerative colitis and Crohn's disease.

  [CARVYKTI] ──INDICATED_FOR──► [Multiple myeloma]
             ──HAS_BOXED_WARNING──► [Boxed warning]
             ──SUPPORTED_BY_EVIDENCE──► [FDA label document]
```

What this lets us do that plain documents cannot:

- **See cross-franchise links:** BIOPATCH (Surgery) and CARTO (EP) are connected **through the procedure**, even though no document mentions both.
- **Know what is *not* approved:** TREMFYA has **no** `INDICATED_FOR` edge to multiple myeloma. So we can say with certainty that it is off-label.
- **Trace impact:** if CARVYKTI's label changes, we follow the edges to every claim, document and procedure connected to it.

### 3.3 The types of things in our graph

These are defined in [schemas.py](../backend/app/models/schemas.py).

- **Node types:** BusinessUnit, Franchise, Product, SoftwareModule, Procedure, Anatomy, ClinicalCondition, EvidenceDocument, BoxedWarning, HardwareCoupling, ClinicalTrial, Publication, SafetySignal, LabelChange, Recall
- **Edge types:**
  - Approval and safety: INDICATED_FOR, CONTRAINDICATED_WITH, HAS_BOXED_WARNING
  - Product relationships: COMPATIBLE_ACCESSORY, INTEGRATES_WITH, PRIMARY_PLATFORM_FOR, POST_OP_INFECTION_CONTROL_FOR
  - Evidence: SUPPORTED_BY_EVIDENCE, STUDIED_IN, CITED_IN
  - Monitoring: HAS_SAFETY_SIGNAL, HAS_LABEL_CHANGE, HAS_RECALL
  - …and a few more

### 3.4 How the graph gets filled

- **Curated starter data** ([seed_data.py](../backend/app/graph/seed_data.py)): J&J products, procedures, conditions and their relationships, entered with explicit types.
- **Public data connectors** that pull from official sources:
  - **openFDA:** FDA's public data
  - **DailyMed:** official drug labels
  - **FAERS:** FDA adverse-event reports for drugs
  - **MAUDE:** adverse-event reports for devices
  - **Recalls:** drug and device recalls
  - **GUDID:** the device ID database
  - **ClinicalTrials.gov:** trials
  - **PubMed:** medical publications
- **Document extraction:** reads label PDFs section by section (e.g. "1 INDICATIONS AND USAGE" becomes INDICATED_FOR edges).
- **Entity resolution:** recognises that "Tremfya", "guselkumab" and "TREMFYA®" are the same product.

### 3.5 Where the LLM fits

The **graph and rules decide the facts** (what is approved, what connects, what the numbers are). The **LLM only phrases the answer** in readable English, using the facts and citations it was given. This is why answers are traceable and much less likely to be hallucinated.

---

## Part 4: How Nexus handles each thing (with where it lives in the code)

### 4.1 Off-label protection (the role gate)

**What it does:** if a **Commercial** user asks about a product for a disease it is **not approved** for, the question is **blocked** and they are told to route it to Medical Affairs / MSL. A **Medical** user asking the same question gets a cited answer, with a flag for review.

**How:**

1. The app finds the product and disease names in the question.
2. It looks up the product's `INDICATED_FOR` edges in the graph (its approved diseases).
3. If the disease is not in that set and the user is Commercial, it blocks the question.

**Code:** `commercial_off_label` and the role check in [supervisor.py](../backend/app/agents/supervisor.py). The guardrail type in the response is `off_label_commercial`.

**Roles available:** `commercial`, `medical`, `mlr`, `admin`.

**Demo:** as Commercial, ask *"Can TREMFYA be used for multiple myeloma?"* and it is blocked. As Medical, ask the same question and you get a cited answer.

### 4.2 MLR Pre-Review (10 automatic checks)

**What it does:** you paste a marketing draft. The app splits it into individual **claims** (sentences that say something about a product) and runs 10 checks. Each finding has:

- a **severity:**
  - *critical:* must fix
  - *warning:* reviewer judgement
  - *unverified:* no evidence found
  - *info:* for awareness
- an explanation
- evidence
- a **suggested fix**
- the **regulation/precedent** behind it

It also gives an overall **risk score (0–100)** and a verdict (ready for MLR or not ready).

**Code:** [checks.py](../backend/app/mlr/checks.py)

| # | Check | What it catches | Uses the graph? |
|---|---|---|---|
| 1 | Absolute claims | "cures", "no side effects", "100% safe" | No (text patterns) |
| 2 | Comparative claims | "superior", "best", "#1", "better than" without head-to-head evidence | Partly |
| 3 | **Off-label** | A disease that is not in the product's `INDICATED_FOR` edges | **Yes** |
| 4 | **Contraindication** | A claim suggesting use where the product is `CONTRAINDICATED_WITH` | **Yes** |
| 5 | **Cross-product** | "Use A together with B" when the graph has no compatibility or integration edge between A and B | **Yes** |
| 6 | Citations | References more than 10 years old | No |
| 7 | **Safety signals** | "Safe / well-tolerated" language for a product that has a boxed warning, FAERS signals or Class I recalls | **Yes** |
| 8 | **Label change** | The product's label recently changed, so the claim must be re-verified | **Yes** |
| 9 | **Safety omission** | The material does not mention the boxed-warning risks | **Yes** |
| 10 | Fair balance | Benefits shown without matching risk information | Partly |

**Sample result (TREMFYA draft in the app):**

- **Before the fix:** NOT READY, risk 99, with 3 critical findings (a cure claim, denying side effects, off-label myeloma) and 3 warnings (2 comparative, 1 cross-product).
- **After the compliant rewrite:** risk 0, ready for MLR.

### 4.3 Procedure bundle builder (cross-selling)

**What it does:** pick a procedure (e.g. AFib ablation) and an annual volume (e.g. 500 cases). The app follows the graph edges from the procedure to every product used in it, **across franchises**. It groups them into capital equipment, software modules, procedural catheters and post-op consumables, then **calculates** the deal value (numbers in Part 2.3).

**Why it matters:**

- The numbers are **computed**, not written by an AI, so they cannot be hallucinated.
- Every product links to its evidence document, e.g. the CARTO IFU or the BIOPATCH dossier.

**Code:** `compute_procedural_bundle` in [queries.py](../backend/app/graph/queries.py), exposed as the `procedural_bundle` tool.

### 4.4 Cited answers (the Co-Pilot)

**What it does:** you ask a question in plain English.

1. A **supervisor** routes it to the right specialist agent: MedTech bundler, pharma clinical, and so on.
2. The agent searches the graph and the documents.
3. It re-ranks the best evidence.
4. It writes an answer **with citations**, a confidence score and a risk level.

**Code:** [supervisor.py](../backend/app/agents/supervisor.py)

### 4.5 Always-current knowledge (label changes, recalls, safety signals)

**What it does:** the connectors re-pull official FDA data, and the app then updates the graph:

- **Label change:** it compares the new label to the old one **section by section** and creates a `LabelChange` node linked to the product.
- **Recall:** it creates a `Recall` node linked to the product.
- **Safety signal:** it creates a `SafetySignal` node from FAERS reports.

Because these are linked in the graph, you can immediately see which procedures, bundles and claims are affected. MLR checks #7 and #8 use this automatically.

**Code:** [evidence_sync.py](../backend/app/ingestion/evidence_sync.py)

### 4.6 Kenvue guard

**What it does:** blocks questions about Kenvue consumer brands (Tylenol, Neutrogena, etc.), because they are no longer J&J products. It also rejects them during data ingestion.

**Code:** `KENVUE_BRANDS` in [seed_data.py](../backend/app/graph/seed_data.py)

### 4.7 Audit log

**What it does:** every query and answer is logged in a hash chain (see Part 2.4), so compliance can prove what was asked, by whom and what was answered.

### 4.8 MCP server: how Nexus "plugs into" chatbots

**What it does:** exposes Nexus features as tools any AI assistant can call. **Code:** [mcp_server.py](../backend/app/mcp_server.py)

| Tool | What it does |
|---|---|
| `graph_search` | Search products, procedures, conditions and evidence |
| `ego_subgraph` | Show everything connected to one node |
| `procedural_bundle` | Calculate a procedure bundle and its value |
| `claim_lineage` | Trace a product's claims back to their evidence |
| `mlr_review` | Run the MLR pre-review |
| `agent_query` | Ask a question and get a cited answer |

**This is the key to the "chatbot" discussion:** J&J can keep its chatbot (e.g. Microsoft Copilot). The chatbot asks Nexus for the facts and Nexus answers with governed, cited facts.

---

## Part 5: The value deck, slide by slide

File: `docs/JnJ-GraphRAG-Nexus-Value-B2B.pptx` (3 slides). Speaker notes are also inside the PowerPoint.

### Slide 1: "Better for J&J's customers, cheaper for J&J to serve"

**The message:** J&J's customers are organisations. Nexus makes their key moments faster and more trustworthy, and it lowers J&J's cost of serving them.

| Card | What it means in plain words | Proof you can show | What to measure in a pilot (KPI) |
|---|---|---|---|
| 1. Faster hospital buying decisions | The hospital committee approving a new heart programme gets one complete, evidence-backed quote for the whole procedure, instead of collecting quotes from several J&J teams | AFib bundle: $451k equipment + $4,695 per case | Days from customer request to quote |
| 2. Bigger, stickier accounts | Because the whole procedure is visible, one J&J team can sell all the products a procedure needs, across franchises. "Stickier" means the customer is less likely to switch, because they buy the whole set. | ~$2.8M first year vs $451k equipment-only | Attach rate, revenue per account |
| 3. Quicker answers to HCPs | Doctors and hospitals ask J&J scientific questions. Medical staff answer faster, with sources. | Search accuracy MRR 0.975 vs 0.57 for chatbot-style search | How long it takes to answer an inquiry |
| 4. Customer material approved sooner | Material for customers (payer decks, hospital dossiers) is cleaned up before MLR, so there are fewer review rounds | Sample draft: 6 issues found; fixed version risk 0 | Review rounds and days per piece of material |
| 5. Faster recall & label response | When the FDA announces a recall or label change, we immediately see which products and procedures are affected, so the right hospitals are told quickly | Recall and LabelChange nodes linked in the graph | Hours until customers are notified |
| 6. Compliant at every touchpoint | Sales reps physically cannot get an off-label answer from the system, and everything is logged | Off-label question blocked for the Commercial role | Number of off-label incidents (target 0) |

**What to say:** "J&J sells to institutions. Every card is a moment where a customer is waiting on J&J. Nexus makes that moment faster and safer, and it costs J&J less staff time."

### Slide 2: "Real-world B2B moments: before vs with Nexus"

Explain one or two rows as a story. Do not read all four.

**Row 1: hospital Value Analysis Committee, new AFib programme**

- **Before:** the EP rep gets a quote for CARTO. Someone else at J&J has to quote the catheters, and someone from the Surgery franchise the BIOPATCH. Compatibility is checked by hand. The hospital waits weeks and gets several partial quotes.
- **With Nexus:** the bundle builder shows the whole procedure in one view, with the items, prices, how each product is used and the evidence.
- **Impact:** the hospital gets one clear quote quickly (better experience). Fewer ordering mistakes and less staff time for J&J (lower cost).
- **Live demo:** yes, this is the bundle builder.

**Row 2: oncology centre P&T committee assessing CARVYKTI**

- **Before:** the hospital's P&T committee asks J&J about CARVYKTI's safety before adding it to their formulary. An MSL searches the label, trials, PubMed and FDA safety reports by hand, and the answer takes days.
- **With Nexus:** a Medical user gets a cited answer showing the boxed warning, REMS requirement and indication from the FDA label. Trials and FAERS safety signals are added once those data sources are synced.
- **Impact:** a faster formulary decision for the hospital, and less search time for the MSL.

**Row 3: payer or IDN reviewing a TREMFYA value deck**

- **Before:** Marketing creates a deck for an insurer or a hospital network. MLR finds problems late ("cures", an off-label mention), and the deck goes back and forth several times.
- **With Nexus:** Pre-Review catches those issues **before** submission and suggests rewrites.
- **Impact:** the customer gets the material sooner, with fewer review rounds and less rework by agencies (the outside firms that design marketing material).

**Row 4: hospital biomed / supply chain hit by an FDA recall or label change**

- **Before:** the J&J regulatory team reads the FDA notice and emails the franchises. People build lists of affected products and materials by hand.
- **With Nexus:** the recall or label change is linked in the graph to the product, its procedures and bundles, so an impact list is available immediately.
- **Impact:** the right hospitals are told first, and patient-safety and liability risk goes down.

**Footnote to say out loud:** "The 'before' timings are typical industry experience. In a pilot we would measure J&J's actual baseline."

### Slide 3: "Not another chatbot: the governed layer that makes chatbots safe"

**The message:** Nexus does not compete with a chatbot. It sits **underneath** the chatbot and gives it trusted facts.

**The left-hand table, row by row:**

| Row | Normal chatbot | Nexus | Plain meaning |
|---|---|---|---|
| Who is asking? | Answers anyone; rules are just written into the prompt and can be bypassed | Role-based gates in code | A rep cannot get an off-label answer, whatever they type |
| Multi-hop questions | Finds similar text; misses links | Follows product → procedure → label | It can answer questions whose answer is a connection, not a sentence |
| Completeness | Only the top 5–10 similar chunks | Every connected item | "List all affected products" gives the full list |
| Current label? | Knowledge may be outdated | Synced from FDA, with change detection | Knows when a label changed |
| Numbers | Can invent them | Calculated from data | Prices and totals are computed, not guessed |
| Repeatability / audit | Varies run to run | Same evidence, cited, logged | You can prove where an answer came from |
| Retrieval quality | 0.57 | 0.975 | Measured on our test set |

**The diagram on the right:**

1. A user types into their usual chatbot (Copilot, Teams).
2. The chatbot calls Nexus over MCP.
3. Nexus applies the graph, role gates, MLR checks, label monitoring, the audit log and the bundle maths.
4. Nexus returns a cited, current, permitted answer, which the chatbot phrases nicely.

**What to say:** "Keep your chatbot as the front door. Nexus is what makes what it says compliant and provable."

---

## Part 6: "Why not just use a chatbot?", explained simply

### The analogy

- A **chatbot** is like a very fast reader with a pile of documents. Ask a question and it finds the pages that **look most similar** to your question, then summarises them.
- A **knowledge graph** is like a **map of how everything connects**: which product is approved for which disease, which products are used together in which procedure, which recall affects which product.

Some questions are answered by **a sentence in a document**. A chatbot is fine for those. Other questions are answered by **a connection between documents, or by the absence of something**. A chatbot cannot reliably answer those. Nexus can.

### The four things a chatbot cannot reliably do

**1. Connect across documents.** No document says "CARTO and BIOPATCH are sold together". The link exists only because both are used in AFib ablation. The graph stores that link; a chatbot never finds it.

**2. Prove something is *not* approved.** This is the strongest point.

- A chatbot looks at its top 5 passages. If "myeloma" is not there, it cannot tell whether that means "TREMFYA is not approved for myeloma" or "I just didn't find the right page". So it may still answer, and it might be wrong.
- The graph holds TREMFYA's **complete list of approved diseases**. Myeloma is not in it, so the answer is a definite "off-label" and the question is blocked.
- The same applies to "Product A works with Product B": if the graph has no compatibility link, the claim is flagged.

**3. Give complete lists.** "Which products are affected by this recall?" A chatbot gives the top few similar passages and might silently miss some. The graph gives every connected product.

**4. Be measurable and auditable.** We measured it: 0.975 vs 0.57 on the same test questions. The same question gives the same evidence. Numbers are calculated, not generated. Every answer is logged.

### Be honest about what a chatbot *can* do

Saying this honestly makes the rest of your answer more credible:

| Benefit | Can a chatbot alone do it? | Why |
|---|---|---|
| Summarise a single document, draft text | ✅ Yes | No connections needed |
| Catch words like "cures" or "no side effects" | ✅ Mostly | Simple text patterns |
| Role-based access, audit log | ⚠️ Possible with engineering | But the off-label block needs to *know* what is approved, and that knowledge comes from the graph |
| Off-label and unsupported-combination detection | ❌ No | Needs proof that something is absent |
| Cross-franchise bundles | ❌ No | The link is not written in any document |
| Recall / label-change impact | ❌ No | Needs to follow chains of connections |
| Complete lists | ❌ No | Top results are not a complete set |

**Your one-liner:** *"A chatbot reads documents. Nexus knows how our products, procedures and approvals connect, and what is **not** connected. Compliance and cross-selling both depend on that, and no document states it."*

---

## Part 7: Questions you will likely be asked

**Q: Is this just another chatbot?**
No. It is the trusted knowledge layer **underneath** chatbots. The chatbot is the interface; Nexus supplies cited, permitted facts. It can plug into Copilot or any assistant through MCP.

**Q: Why not put all documents into a chatbot with a big memory (long context window)?**

- It is expensive for every question.
- There is still no guarantee the model uses the right part.
- It still cannot prove that something is *not* approved.
- There is no audit trail.

**Q: Why not train (fine-tune) an AI model on J&J documents?**
It would be out of date the day a label changes, and it cannot show where an answer came from. Regulated content needs citations.

**Q: Does it replace MLR reviewers?**
No. It is a **pre-review**. Humans still approve everything. It just means drafts arrive cleaner, so there are fewer rounds.

**Q: Where does the data come from?**
Today: curated POC data plus official public sources (FDA, DailyMed, FAERS, MAUDE, recalls, ClinicalTrials.gov, PubMed). In a pilot: J&J's internal systems (approved claims library, price lists, content management).

**Q: Are these real prices?**
No. They are illustrative list prices for the POC. Real contract prices would come from J&J systems.

**Q: How accurate is it?**
On our 40-question test set:

- search accuracy (MRR) is 0.975 vs 0.57 for typical chatbot search;
- the right document is in the top 5 for 98.8% of questions;
- answers are grounded in evidence 100% of the time.

Measuring on J&J's own questions would be part of a pilot.

**Q: What if the graph is wrong or incomplete?**
Then the answer is wrong in a **visible, traceable** way. You can see the exact edge and source document, and fix it once for everyone. With a chatbot, errors are hidden inside the model. A pilot would also include review workflows for graph updates.

**Q: Which AI model does it use? What does it cost?**
It works with any LLM, and the LLM only phrases answers. The POC uses no paid licences.

**Q: Is it secure / compliant itself?**

- Access depends on the user's role.
- Every query is logged in a tamper-evident audit log.
- Prompt-injection attempts (people trying to trick the AI) are blocked.
- Kenvue brands are out of scope.
- Production security (single sign-on, hosting) would be set up in a pilot.

**Q: Why is it needed now?**

- AI chatbots are being rolled out across companies anyway.
- Without a governed layer, they will give uncited, possibly off-label answers to sales staff.
- Nexus lets J&J adopt AI safely.

---

## Part 8: What is real vs what is estimated (do not overclaim)

| Statement | Status |
|---|---|
| Off-label block for Commercial; cited answer for Medical | ✅ Working in the app, can be shown live |
| MLR sample: risk 99 with 6 issues; fixed version risk 0 | ✅ Working, can be shown live |
| AFib bundle maths ($451k, $4,695/case, ~$2.8M) | ✅ Working, but **prices are illustrative** |
| MRR 0.975 vs 0.57, etc. | ✅ Measured, **on our 40-question POC test set** |
| Label change / recall / FAERS sync | ✅ Built; needs the connectors to be run to show synced data |
| CARVYKTI boxed warning, REMS, indication | ✅ In the graph today |
| CARVYKTI trials and FAERS signals | ⚠️ Only after running those syncs |
| "Before" timings (weeks, days) | ⚠️ Typical industry experience, **not J&J measurements** |
| KPIs on slide 1 | ⚠️ What we *would measure* in a pilot, not results |
| J&J internal data integration, SSO, production hosting | ❌ Not built; pilot scope |

---

## Part 9: Live demo script (about 5 minutes)

**1. Off-label gate (1 minute)**

1. Set the role to **Commercial**.
2. Ask: *"Can TREMFYA be used for multiple myeloma?"* The request is **blocked**, with the reason: not in approved labeling, route to Medical.
3. Switch the role to **Medical** and ask the same question. You get a cited answer with a review flag.
4. Say: "The block is based on the graph's list of approved uses, not on a prompt. A chatbot cannot guarantee this."

**2. MLR Pre-Review (2 minutes)**

1. Open MLR Pre-Review and load the TREMFYA sample.
2. Show the result: **NOT READY, risk 99**, 3 critical and 3 warnings. Click the off-label finding and show the evidence and regulation.
3. Paste the compliant rewrite and show **risk 0, ready for MLR**.
4. Say: "This doesn't replace MLR. It means drafts arrive clean, with fewer rounds."

**3. Procedure bundle (2 minutes)**

1. Open the Bundler, pick **AFib ablation** and set **500 cases**.
2. Show the four groups:
   - CARTO 3 V8 plus its 5 software modules;
   - VIZIGO and AcuNav (procedural catheters);
   - BIOPATCH (from a different franchise).
3. Show the numbers: $451k capital, $4,695 per case, ~$2.8M in year 1 (illustrative).
4. Say: "No document links CARTO to BIOPATCH. The graph does, through the procedure. That's the cross-franchise opportunity."

**Close:** "Keep your chatbot as the front door. Nexus makes what it says compliant, complete and provable. We propose a pilot on one franchise to measure the real J&J baseline."

---

## Quick reference: the 30-second explanation

> J&J sells to hospitals, health systems and insurers. Answering their questions, quoting procedures and approving marketing material all depend on people searching thousands of documents across separate teams. That is slow, misses cross-team sales, and risks saying something not approved by the FDA. Nexus connects J&J's products, procedures, approvals and safety data into a knowledge graph. It answers with citations, blocks off-label answers for sales, pre-checks marketing before legal review, and calculates full procedure bundles. It doesn't replace your chatbot; it makes your chatbot safe.
