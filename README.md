# Lease Intelligence Platform

Staff take-home: ingest commercial lease PDFs, extract structured terms with an LLM
pipeline, and store provenance-backed fields in Postgres so critical dates can be
acted on — not guessed.

**Live (Railway → Neon):** https://lease-intelligence-platform-production.up.railway.app  
**Demo login:** `admin` / `newmark`  
**Interactive API:** [Swagger UI](https://lease-intelligence-platform-production.up.railway.app/docs) at `/docs`

What is deployed today is the **extraction API** (auth, upload, extract, leases,
fields, obligations). The React UI and Spring risk-engine are scaffolded in-repo
and run under `docker compose`; they are not the public Railway surface yet.

---

## The problem

This targets **occupier lease administration** — corporate tenants managing a
portfolio of leases. The expensive failure mode is missing a **renewal-notice
window**: miss the deadline and a renewal right can vanish (seven-figure
exposure). Manual lease abstraction does not scale across hundreds of documents
with amendments and inconsistent drafting.

I chose this over alternatives I researched (CAM/opex audit tooling, data-room
diligence Q&A) because the value proposition is concrete and demoable: low
document volume, very high dollar value per miss, and a clean split between
probabilistic extraction and **deterministic** deadline logic. CAM audit needs
invoice-level financial systems; diligence Q&A is useful but does not force the
provenance + confidence + rules-engine discipline this problem demands.

---

## Architecture (what ships)

```
PDF → loader → sectioner → router → budget → extractor
    → output guardrails → consolidator → persist
         │                                    │
         └──────── Neon Postgres ◄────────────┘
                   (single source of truth)
```

- **loader** — pdfplumber text per page; scanned pages flagged (no OCR).
- **sectioner / router / budget** — heading tags + `field_matrix.yaml` route
  context per field group; tiktoken budget drops lowest-relevance sections first.
- **extractor** — LangChain + Claude, temperature 0, one structured call per
  field group (parties, term, financial, options, opex).
- **guardrails** — input (`FileGuard`, `InjectionScan`); output (`SchemaGuard`,
  `SanityGuard`, `CitationGuard`, `ConfidenceGate`). PDF text is **untrusted
  data**, never instructions (prompt templates say so explicitly).
- **consolidator / persist** — latest-document-wins per field; every field
  stores value, confidence, page, snippet, prompt version, model; obligations
  derived from effective fields; append-only `events` via `EventPublisher`
  (`PostgresEventPublisher` today — Kafka is an ops swap behind the interface).

Local stack: `docker compose` (gateway, extraction, risk-engine scaffold, web
scaffold, Postgres). Production DB is **Neon (pgvector)**. Runbook:
[`deploy/railway.md`](deploy/railway.md).

---

## Assumptions and tradeoffs

- **Synchronous extraction** in the request/seed path — simple and demoable;
  long PDFs block that worker; background seed never blocks API listen.
- **No OCR** — text-layer PDFs only; scanned pages are flagged, not invented.
- **Latest-wins consolidation** across base + amendments — honest for the demo;
  true legal merge needs humans.
- **Single demo user** (JWT HS256) — not multi-tenant auth.
- **Postgres-as-queue** — `events` table instead of a broker.
- **Embeddings / Q&A optional** — extraction succeeds without OpenAI; chunk
  embed skips on missing key / API errors (`ENABLE_QA`).
- **Nested-schema non-determinism** — Claude sometimes returns empty/partial
  structured objects; mitigated with retries, timeouts, and graceful null-leaf
  degradation (not perfect — see “next”).
- **Ephemeral PDF disk on Railway** — content-hash paths; seed re-ingests on
  boot (D11). Production would be object storage.

---

## Evaluation

Level 1 harness lives in `services/extraction/evals/` (`python -m evals.run`):
offline compare of DB effective fields vs gold, per-group accuracy, page-citation
accuracy, and a **confidence calibration table** (the headline artifact).

**Current report:** [`EVAL_REPORT.md`](EVAL_REPORT.md) — harness is in place;
gold labeling / first scored run is still pending, so there are **no headline
accuracy numbers or calibration cells yet**. After the first labeled run, that
file will list overall/group accuracy, calibration buckets, and auto-listed
known failure cases (field / gold / extracted). Levels 2–3 (retrieval /
faithfulness) are stubbed while Q&A embeddings stay optional.

---

## What I’d build next (ranked)

1. Reliability on nested-schema extraction (schedules, renewal options)
2. OCR lane for scanned pages
3. Tighter `CitationGuard` (fewer false needs-review)
4. Finish risk-engine + Portfolio / Lease / Alerts dashboard
5. Kafka (or similar) behind `EventPublisher` at scale
6. OIDC auth
7. Drift monitoring on extraction confidence distributions

---

## Run locally

```bash
cp .env.example .env   # set ANTHROPIC_API_KEY (OPENAI_API_KEY optional for Q&A)
docker compose up --build
```

- App gateway: http://localhost:8080  
- Extraction health: http://localhost:8080/api/health  
- Swagger (extraction direct): http://localhost:8000/docs when hitting the
  service container / local uvicorn  

Eval (against a DB with effective fields + gold JSON):

```bash
cd services/extraction
python -m evals.stub <lease_id>   # pre-fill gold for hand-labeling
python -m evals.run --all         # writes ../../EVAL_REPORT.md
```

---

## Built with AI — process record

This repo was built with AI assistance (Cursor). The durable record of decisions
and how work was done:

- [`docs/DECISIONS.md`](docs/DECISIONS.md) — numbered design decisions (D1–D17+)
- [`docs/transcripts/`](docs/transcripts/) — session transcripts / process notes

Agent conventions and the product contract live in [`AGENTS.md`](AGENTS.md).
