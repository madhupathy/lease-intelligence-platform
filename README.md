# Lease Intelligence Platform

**Live demo:** open [/app](https://lease-intelligence-platform-production.up.railway.app/app),
log in `admin` / `newmark` → five real leases extracted with per-field confidence,
provenance, and derived renewal-notice obligations.

Staff take-home for a CRE firm: ingest commercial lease PDFs, extract structured
terms with an LLM agent, and persist provenance-backed fields so critical dates
can be reviewed and acted on. **What is live today** is the extraction API
(auth, upload, extract, leases, fields, obligations) on Railway against Neon
Postgres, plus a **vanilla JS standalone dashboard** served same-origin at
`/app`. The full React/Vite dashboard remains a local scaffold only. Q&A /
embeddings are optional and currently disabled. The Spring risk-engine is
scaffolded for compose, not the public Railway surface.

**Live:** https://lease-intelligence-platform-production.up.railway.app  
**Dashboard:** https://lease-intelligence-platform-production.up.railway.app/app  
**Demo:** `admin` / `newmark`  
**API docs:** [/docs](https://lease-intelligence-platform-production.up.railway.app/docs) (Swagger)
<br>
<img src="docs/screenshots/portfolio.png" width="700"><br>
<img src="docs/screenshots/lease-detail.png" width="700">


---

## The problem

This serves **occupier lease administration** — corporate tenants running a
portfolio of leases. The failure mode that matters is a missed **renewal-notice
window**: miss it and the renewal right can be forfeited (seven-figure exposure).
Manual lease abstraction does not scale across amendments, inconsistent
drafting, and portfolio volume.

I chose this over alternatives I researched (**CAM reconciliation audit**,
**due-diligence data-room agent**) because the value is concrete and demoable:
low document count, very high dollar value per miss, and a clean split between
probabilistic extraction and deterministic deadline logic. CAM audit needs
invoice-level financial systems; a data-room agent is useful for search but does
not force provenance, confidence gating, and a rules path for legal deadlines.

---

## Architecture

**Deployed today**

```
  browser ──▶  extraction-svc (FastAPI + Claude)
               │  /api/*   REST (auth, leases, extract)
               │  /docs    Swagger
               │  /app     vanilla JS dashboard
               └──────────▶ Neon Postgres (pgvector)
                            single source of truth
```

**Full topology (local / target)**

```
                        ┌─────────────────────────────┐
  browser ──────────▶   │  gateway (nginx) :8080      │
                        │  /            → web         │
                        │  /api/auth/*  → extraction  │
                        │  /api/*       → extraction  │
                        │  /api/alerts* → risk-engine │
                        └──────┬──────────────┬───────┘
                               │              │
              ┌────────────────▼───┐   ┌──────▼────────────┐
              │ extraction-svc      │   │ risk-engine       │
              │ Python 3.12 FastAPI │   │ Java 21 Spring    │
              │ LangChain + Claude  │   │ Boot 3, @Scheduled│
              │ pgvector Q&A        │   │ deterministic     │
              └────────────┬────────┘   └──────┬────────────┘
                           │                   │
                        ┌──▼───────────────────▼──┐
                        │ Postgres (Neon, pgvector)│
                        │ single source of truth   │
                        └──────────────────────────┘
  web (compose target) = React/Vite scaffold via gateway;
  live UI today = vanilla JS at extraction /app
```

**Extraction pipeline:**  
`loader → sectioner → router → budget → extractor → guardrails → consolidator → persist`

- **Neon Postgres** is the single source of truth (local compose uses
  `pgvector/pgvector`).
- **Events:** append-only `events` table behind an `EventPublisher` interface —
  Kafka is an ops swap, not a code change.
- **Provenance + confidence** on every field (value, confidence, page, snippet,
  prompt version, model); `ConfidenceGate` marks `needs_review` below threshold.
- **Untrusted PDF text:** document body is data, never instructions;
  `InjectionScan` flags injection heuristics; prompts put lease text inside
  `<document>` delimiters.
- **Data ingestion:** PDF upload works today via `POST /api/leases` (and Swagger).
  A `DocumentSource` abstraction is the intended seam so a Kafka consumer or
  S3/SharePoint loader is another implementation; the `events` table +
  `EventPublisher` interface are the integration point for database/event
  connectors (future).

---

## Assumptions and tradeoffs

- **Synchronous extraction** — fine for demo scale; long PDFs occupy a worker.
- **No OCR** — text-layer PDFs only; scanned pages are flagged, not invented.
- **Latest-wins** amendment consolidation — honest for the demo; real legal
  merge needs humans.
- **Single demo user** (JWT) — production path is OIDC.
- **Postgres-as-queue** instead of Kafka for events.
- **Embeddings / Q&A optional and currently disabled** — extraction still runs;
  Level 2–3 evals are stubbed.
- **Nested-schema non-determinism** (schedules, renewal options) handled by
  retry-with-reinforcement, request timeouts, and graceful degradation to null
  leaves + `needs_review` — not perfect yet.

---

## Evaluation

Full write-up: [`EVAL_REPORT.md`](EVAL_REPORT.md) (Level 1, offline vs gold,
`claude-sonnet-4-6`, prompt `v1.0`, 1 lease / 18 fields —
`crowdstrike_capitol_tower_austin_lease`).

| Metric | Value |
|--------|-------|
| Overall field accuracy | **72.2%** |
| Page-citation accuracy | **61.5%** |
| Fields scored | 18 |
| Failures | **5** |

The 72.2% is a single run where the financial group hit its known
non-deterministic empty-output path (a prior run extracted those fields
correctly); the headline is that every genuine miss was a zero-confidence
abstention, not a wrong answer.

**Per-group:** parties / term 100%; opex 75%; options 66.7%; **financial 25%**
(systematic weak spot — nested-schema empty output).

**Confidence calibration:** high-confidence fields (≥0.9) were 100% accurate;
failures concentrate in the low-confidence buckets. The three genuine misses
(`base_rent_schedule`, `escalation_type`, `security_deposit`) were all
**0.0-confidence abstentions** — the model declines rather than hallucinates,
which is what makes the `needs_review` queue meaningful.

**Known failure cases:**
- Genuine (financial nested-schema empty): `base_rent_schedule`,
  `escalation_type`, `security_deposit`
- Measurement artifacts (noted honestly, not tuned away): `renewal_options`
  (list-shape comparison vs gold simplification), `cam_structure` (gold
  ambiguity — `gross` vs extracted `base_year`)

---

## What I’d build next (ranked)

1. Reliability of nested-schema extraction (rent schedules, renewal options)
2. OCR lane for scanned pages
3. Tighter `CitationGuard` (over-penalizes correct fields to 0.3 on prose-heavy snippets)
4. Risk-engine + React dashboard to close the alert loop
5. Kafka for portfolio-scale ingest
6. OIDC auth
7. Drift monitoring on extraction confidence over time

### Observability (priority — my domain)

Today: structured logs (guardrail penalties, per-group success/empty, tokens per
run). Next: OpenTelemetry spans across the agent pipeline (one span per stage:
loader → sectioner → router → budget → extractor → guardrails → persist);
Prometheus/Grafana metrics (latency, tokens, confidence distribution,
`needs_review` rate, group-empty rate); per-run trace links. Nested-schema empty
output becomes a first-class signal, not something inferred from logs.

### Cost tracking

Tokens in/out are already persisted on each `extraction_run`. Next: a per-model
$/token cost model rolled up to cost-per-lease and cost-per-portfolio, with budget
alerts — extending the idempotency cache that already avoids re-extraction spend.

### Evaluation depth

Today: Level 1 (gold field accuracy + confidence calibration) on a hand-labeled
lease. Next: gold across all five seed leases; Level 2 (recall@k, MRR) and Level 3
(LLM-judge faithfulness) once embeddings are funded; CI regression gates on
prompt-version bumps; extraction determinism tests (same input × N, measure
variance) to quantify nested-schema non-determinism.

### RAG / Retrieval roadmap

The retrieval (Q&A) layer is scaffolded but currently disabled (embeddings
unfunded); these are the improvements it needs to be production-grade:

1. **Hybrid search.** Today: pure semantic (pgvector cosine). Legal text relies on
   exact terms of art (“Base Rent”, “Commencement Date”) where lexical/BM25 often
   beats vector search. Next: hybrid retrieval (BM25 + vector, reciprocal-rank
   fusion), validated against a retrieval eval — I expect it to outperform pure
   semantic on this document type.

2. **Retrieval evaluation.** Today: Level 2/3 evals are stubbed. Next: recall@k
   and MRR against a labelled gold Q&A set, and generation faithfulness via an
   LLM-judge — so retrieval quality is measured, not assumed. This also lets me
   justify embedding-model and chunk-size choices empirically instead of by
   default.

3. **Semantic response cache (cost).** Today: no Q&A response caching — repeated
   questions hit the LLM every time. Next: embed the incoming question and return a
   cached answer when a prior question is above a similarity threshold; combine
   with per-lease scoping. Extends the existing content-hash idempotency cache
   (extraction) and embedding cache (chunks).

4. **Prompt caching.** Today: not used. The extraction and Q&A prompts have a large
   static prefix (schema + instructions + injection notice). Next: enable
   Anthropic prompt caching on that prefix to cut input-token cost and latency on
   every call — a near-free win given the stable prompt structure.

5. **Chunking & embedding tuning.** Today: section-aware recursive chunking
   (~800 tokens, 100 overlap) chosen because leases carry explicit structural
   boundaries (Articles/Sections); OpenAI `text-embedding-3-small` at native 1536
   dims chosen for no-padding + cost. Chunking feeds the Q&A retrieval path only;
   primary field extraction uses section-routed structured extraction, not RAG.
   Next: tune chunk size/overlap and compare embedding models against the retrieval
   eval above, rather than relying on sensible defaults.

---

## Running it

**Quick path:** open the live URL → `/docs` → Authorize with `admin` / `newmark`.

**Local:**

```bash
cp .env.example .env   # ANTHROPIC_API_KEY required for real extract/seed
docker compose up --build
```

App: http://localhost:8080 · Health: `/api/health` · Env names: [`.env.example`](.env.example)  
Deploy notes: [`deploy/railway.md`](deploy/railway.md)

```bash
cd services/extraction
python -m evals.stub <lease_id>
python -m evals.run --all    # refreshes EVAL_REPORT.md
```

### How this was built

Developed with AI assistance (Claude for design; Cursor / Opus for
implementation). Design decisions are recorded in
[`docs/DECISIONS.md`](docs/DECISIONS.md) as the engineering record — per the
assignment’s request to retain how the system was built with AI. Product
contract and conventions: [`AGENTS.md`](AGENTS.md).
