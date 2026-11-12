# J&J GraphRAG Nexus: POC Pitch and Robustness Analysis

> **Summary:** a single, cited knowledge layer that connects J&J Innovative Medicine and J&J MedTech
> products to procedures, anatomy, conditions and regulatory evidence. Field, medical and commercial teams
> could use it to:
> - assemble **cross-sector bundles**
> - **answer clinical questions with citations**
> - **pre-screen promotional claims against the label**
>
> These tasks typically take hours today, spread across siloed systems; the POC does them in seconds.

All money figures in this document are **illustrative assumptions** for discussion. Replace them with
your function's own baselines before the review. Section 4 gives every formula so the model can be re-run.

---

## 1. The problem (why now)

| Pain point | Who feels it | Today |
|---|---|---|
| Product knowledge is siloed by franchise and sector (IM vs MedTech, EP vs Ortho vs Surgery). | Key account managers, field sales | Reps know their own bag. Cross-franchise and cross-sector opportunities in the same procedure are missed. |
| Answering "which products are used in procedure X, and what evidence supports them?" | Medical affairs, MSLs, medical information | Manual search across PI PDFs, IFUs, DailyMed and intranet pages. |
| Checking that a promotional claim matches the current label (boxed warnings, indications). | MLR (Medical-Legal-Regulatory) reviewers | Line-by-line manual reading against the PI/IFU. Slow, and the main bottleneck for content throughput. |
| Separating the portfolio from Kenvue after the 2023 separation. | Commercial ops, data stewards | Legacy consumer brands still appear in content, data feeds and search. |
| Gen-AI chatbots built on plain vector RAG. | IT / AI CoE | Hallucinations, no traceability, cannot do multi-hop reasoning (product → procedure → anatomy → risk). |

## 2. What the POC already proves (working demo)

| Capability | What to show in the demo | Business meaning |
|---|---|---|
| **Typed knowledge graph** (97 curated nodes / 145 edges; grows with live sync) | Graph Explorer → search "CARTO" → click a node → 1-hop/2-hop spotlight and inspector with evidence | One connected view of the portfolio, with source provenance on every fact |
| **Procedural Cross-Sell Bundler** | AFib ablation @ 500 procedures → 4-tier bill of materials (capital, software, disposables, Ethicon post-op) with ROI | Turns a single capital sale into a full-procedure value proposition across franchises |
| **Multi-agent Co-Pilot** (LangGraph router → specialist agent → synthesiser) | "Regulatory Auditor" preset → ranked evidence and claim-provenance table | Answers include citations; no ungrounded free text |
| **Claim Auditor** | Audit table: claim, claim type, evidence source, verified/flagged status | MLR pre-screening before human review |
| **Live ingestion** | Sync jnj.com (51 products parsed) and NIH DailyMed (CARVYKTI label PDF → sections → graph) | Knowledge stays current with the public label of record |
| **Kenvue guardrail** | Try ingesting "Tylenol" → rejected, 0 nodes added | Enforces the post-separation portfolio boundary automatically |
| **Runs fully offline** | No API keys needed | Zero licence cost for the POC; no data leaves the laptop |

**Engineering evidence:** 36 automated end-to-end tests pass and the production frontend build is clean.
The stack is open source (FastAPI, NetworkX/Neo4j, LangGraph, React).

## 3. Collaboration value: IM × MedTech, and J&J × partners

This is the main argument. The graph's value comes from **connections that no single franchise owns**.

### 3a. Inside J&J (cross-sector synergy)

- **Procedure-centric selling.** A single procedure node (for example AFib ablation) connects:
  - Biosense Webster capital and software
  - EP catheters
  - ICE ultrasound
  - Ethicon post-op consumables

  The bundler makes "attach rate" visible and quantifiable for each account.
- **IM ↔ MedTech bridges.** Conditions and anatomy are shared nodes. This lets you ask, for example, "which
  oncology therapies and which surgical/interventional devices touch the same patient pathway?" That is the
  starting point for joint account plans and joint medical education.
- **Shared evidence layer.** Medical affairs curates evidence once. Sales, marketing and MLR all consume
  the same cited facts, which reduces duplicate content and conflicting messages.
- **Reusable platform.** The ingestion, retrieval, agents and guardrails are franchise-agnostic. A new
  franchise is a data-onboarding task, not a new build.

### 3b. With external collaborators

| Collaborator | How the graph helps |
|---|---|
| **Hospitals / IDNs** | Procedure-level total-cost-of-care bundles support value-based contracting and capital committee conversations |
| **GPOs / procurement** | A transparent bill of materials per procedure simplifies contract tiering |
| **Regulators / public data (FDA DailyMed, openFDA, GUDID, ClinicalTrials.gov)** | Uses the label of record directly, so claims always trace back to official sources |
| **Academic / KOL partners** | Evidence nodes can link to trials and publications, which supports evidence-gap analysis |
| **Cloud / AI partners (for example Azure OpenAI)** | The architecture swaps in an enterprise LLM and a managed graph without code redesign |

## 4. Value model (illustrative; replace with real baselines)

### 4a. Productivity (cost avoidance)

| Lever | Formula | Example assumptions | Annual value |
|---|---|---|---|
| Field search and prep time | reps × hrs saved/wk × weeks × loaded $/hr | 150 × 2 × 46 × $90 | **$1,242,000** |
| Medical information / MSL response time | users × hrs saved/wk × weeks × $/hr | 40 × 3 × 46 × $120 | **$662,400** |
| MLR pre-screen | claims/yr × hrs saved/claim × $/hr | 1,200 × 1.5 × $150 | **$270,000** |
| **Subtotal (pilot-scale)** | | | **≈ $2.17M / yr** |

### 4b. Revenue (growth)

- **Bundle attach.** The demo shows one AFib account at 500 procedures/yr totalling about $2.8M in deal value,
  with the cross-sell portion about 5.2× the capital-only baseline (illustrative list prices).
- **Conservative pilot target:** 2–3 incremental consumable/software attach deals per region per year.
  - The formula is `deals × avg consumable pull-through`.
  - For example, 3 × $250k = **$750k/yr per region**.

### 4c. Risk reduction (hard to price, but often the strongest argument for approval)

- Fewer off-label or outdated claims reaching MLR or the market, because every claim is linked to the current PI.
- An automated Kenvue boundary prevents brand-misattribution errors after the separation.
- Full provenance (source URL, document, section) for every answer makes the system audit-ready.

### 4d. Cost to run

| Phase | Cost drivers | Indicative range (validate with Azure Pricing Calculator) |
|---|---|---|
| POC (today) | Laptop, open source | ~$0 licence |
| 10–12 wk pilot | 2–3 FTE plus a small Azure footprint (Container Apps, managed Neo4j/Cosmos, Azure OpenAI, Key Vault, App Insights) | Low thousands of $/month in cloud spend; people cost dominates |
| Scale | SSO, CRM/ERP integration, MLR workflow, support | Business case at the pilot exit gate |

**Payback logic:** even if only 20% of the productivity estimate is realised (~$435k), that covers a
typical pilot budget within the first year, before any revenue upside is counted.

## 5. Why GraphRAG, and not just a chatbot

| | Plain LLM chatbot | Vector RAG | **GraphRAG Nexus** |
|---|---|---|---|
| Multi-hop questions (product → procedure → anatomy → risk) | ✗ | Weak | ✓ explicit traversal |
| Citations / provenance | ✗ | Chunk-level | ✓ node, edge and document lineage |
| Deterministic numbers (bundle prices, ROI) | ✗ hallucinated | ✗ | ✓ computed from the graph |
| Business-rule guardrails (Kenvue, label status) | Prompt only | Prompt only | ✓ enforced in code at ingestion and query time |
| Explainability for MLR and audit | Low | Medium | High: the retrieval path is shown in the UI |

## 6. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Hallucinated or off-label output | Grounded generation only from retrieved graph facts. The claim auditor flags anything unsupported. A human (MLR) stays in the loop. |
| Data accuracy (curated prices are estimates) | The pilot replaces them with SAP/ERP list prices and MDM product masters (see §7 P0). |
| Website scraping is fragile or restricted (jnjmedtech.com returns 403) | Move to sanctioned sources: internal product master, GUDID (devices), DailyMed/openFDA (drugs). |
| Security / compliance | No PHI or PII is used. Add Entra ID SSO, RBAC, private endpoints and audit logging before user access. |
| Adoption | Embed in existing tools (CRM / Teams) and pick 1–2 high-pain use cases for the pilot. |

## 7. Robustness gap analysis (what to add to the POC)

The items are ranked by how much each raises the approval odds relative to effort.

### P0: needed for an approvable pilot (2–4 weeks)

1. **Evaluation harness (proof of quality).** Have SMEs write a golden set of 50–100 Q&A pairs. Measure:
   - retrieval recall@k
   - answer faithfulness / groundedness (for example RAGAS-style metrics)
   - citation accuracy
   - claim-audit precision/recall

   Run it in CI. *Managers approve numbers, not demos.*
2. **Sanctioned data sources instead of scraping:**
   - **FDA AccessGUDID API** for MedTech device identifiers. This solves the jnjmedtech.com 403 cleanly.
   - **openFDA** drug labels, FAERS adverse events, MAUDE device events, and recalls/enforcement.
   - Internal product master / SAP pricing (read-only extract) in place of the illustrative prices.
3. **Label-change monitoring.** Schedule DailyMed/openFDA syncs and diff label sections between versions. Alert
   when a boxed warning or indication changes and list the affected claims and content (strong MLR value).
4. **Security baseline:**
   - Entra ID SSO and role-based views (sales vs medical vs MLR firewall)
   - secrets in Key Vault
   - an audit log of every query, answer and citation
   - prompt-injection sanitising of ingested text
5. **Enterprise LLM switch.** Use Azure OpenAI behind a private endpoint for answer synthesis, keeping the
   deterministic fallback for offline use and regression tests.

### P1: makes it compelling (pilot phase)

6. **Reimbursement layer.** Add CPT/HCPCS/DRG code nodes to procedures so the bundler shows hospital
   economics (reimbursement vs bundle cost). This is very persuasive for IDN conversations.
7. **Clinical evidence layer.** Add ClinicalTrials.gov and PubMed nodes linked to products and indications, with
   evidence-gap detection ("indication with no Phase III evidence node").
8. **MLR workflow.** Export the claim-audit table as a pre-review package (PDF/Excel) and record reviewer
   decisions back into the graph as a learning signal.
9. **Proposal export.** Export a bundle as a customer-ready PDF/PowerPoint, and push it to CRM (Veeva/Salesforce) as an opportunity.
10. **Feedback loop.** Add 👍/👎 and corrections on answers, plus a dashboard of usage, adoption and time-saved estimates.
11. **Graph versioning.** Add bitemporal snapshots so you can ask "what did the label say on date X?". This matters for audit.

### P2: production hardening (scale decision)

12. **Hosting.** Managed graph (Neo4j AuraDB or Cosmos DB Gremlin), Azure Container Apps, autoscaling and caching.
13. **Observability.** Application Insights tracing for each agent step, latency/cost SLOs and load tests.
14. **Quality gates.** Frontend tests (Vitest/Playwright), SAST and dependency scanning (SonarQube) and IaC (Bicep) in the pipeline.
15. **Multi-region / multi-language.** Add EU SmPC and Japan PMDA labels for global teams.
16. **Bring-your-own-data connectors.** SharePoint, Veeva Vault PromoMats and internal IFU repositories.

## 8. Pilot proposal (the "ask")

- **Scope:** 1 procedure family (for example EP / AFib) plus 1 IM therapeutic area (for example oncology), 1 region.
- **Users:** about 20 reps/KAMs, 5 MSLs and 2–3 MLR reviewers.
- **Duration:** 10–12 weeks.
- **Asks:**
  - read access to the product master and list prices
  - an Azure subscription / sandbox
  - 2 h/week of time from an MLR SME and a medical affairs SME
  - an executive sponsor in commercial excellence

### Exit criteria (agree these up front)

| KPI | Target |
|---|---|
| Answer groundedness on the golden set | ≥ 95% |
| Citation accuracy | ≥ 98% |
| Time to answer a procedure/evidence question | −70% vs baseline |
| MLR pre-screen catches (claims flagged that the reviewer agrees with) | ≥ 80% precision |
| Weekly active pilot users | ≥ 60% |
| Bundle proposals generated / attach opportunities logged | ≥ 10 |

## 9. A 5-minute demo script

1. **(30s) The problem:** "Where do our products meet in an AFib procedure, and can we prove every claim?"
2. **(60s) Graph Explorer:** search CARTO → click → spotlight shows the platform, software, catheters, anatomy and
   evidence across franchises.
3. **(90s) Bundler:** AFib at 500/yr → 4 tiers → total deal value and uplift. Drag the volume slider.
4. **(90s) Co-Pilot:** run the *Regulatory Auditor* preset → routing → cited evidence → claim audit table.
5. **(30s) Guardrails:** ingest "Tylenol" → rejected (Kenvue). Sync DailyMed → a fresh label lands in the graph.
6. **(30s) The ask:** pilot scope, KPIs, timeline (§8).

## 10. Talking points for likely objections

- **"Isn't this just another chatbot?"** No. The answers are computed from a governed graph with provenance,
  and the numbers are deterministic. The LLM is optional, and it phrases the answer; it is not the source of truth.
- **"Compliance will block it."** It uses public label data only, enforces guardrails in code and keeps MLR in the loop. It is designed for audit.
- **"Will it scale?"** The storage layer already mirrors to Neo4j, and ingestion and agents are franchise-agnostic.
- **"What does it cost?"** The POC cost $0 in licences, and the pilot spend is mostly people time. Payback comes from productivity alone.
