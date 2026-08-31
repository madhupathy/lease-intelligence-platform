# Railway Deploy Runbook

Railway deploy is a **config change**, not a code change (`AGENTS.md` §3, §6). Local
`docker-compose` stays the source of truth for behavior; Railway wires the same
images to **Neon Postgres (pgvector)** and private networking.

**Never put secrets in the repo.** Set credentials only as Railway service variables
(or a linked Neon plugin). Values below are **names only**.

---

## Architecture on Railway

| Railway service | Image / Dockerfile | Public? | Talks to |
|-----------------|--------------------|---------|----------|
| **extraction** | `services/extraction/Dockerfile` (build context = **repo root**) | optional (see first deploy) | Neon |
| **risk-engine** | `services/risk-engine/Dockerfile` (context = `services/risk-engine`) | no (private) | Neon |
| **gateway** | `gateway/Dockerfile` (build context = **repo root**; embeds `web` build) | **yes** (browser) | extraction + risk-engine over private network |

Postgres is **not** a Railway Postgres plugin in this design: use **Neon** with the
`pgvector` extension enabled (Neon supports it). Local compose still runs
`pgvector/pgvector:pg16`.

---

## First deploy: extraction only

Validate migrations, demo user, seed PDFs, and API output **before** wiring gateway
or risk-engine.

1. Create a Railway project; connect this GitHub/repo.
2. Create **one** service named `extraction`.
3. Settings:
   - **Root Directory:** empty / `.` (repository root — required so `seed/` copies).
   - **Config File:** `services/extraction/railway.toml`  
     (or leave default and use root `railway.toml`, which points at the same Dockerfile).
   - **Builder:** Dockerfile (`services/extraction/Dockerfile`).
4. Generate a **public** domain on the extraction service (temporary).
5. Set extraction env vars (table below). Use Neon URLs in the correct form.
6. Deploy. Watch logs for:
   - `alembic upgrade head`
   - demo user seed
   - portfolio seed (runs only if `leases` is empty **and** both `ANTHROPIC_API_KEY` and
     `OPENAI_API_KEY` are set)
7. Smoke against the public extraction URL:

```bash
# From a machine with curl + python3
export DEMO_USER=...   # same as Railway
export DEMO_PASSWORD=...
bash scripts/smoke.sh https://<extraction-public-host>
```

8. Only after smoke passes: add `risk-engine` and `gateway`, then **remove** the
   public domain from extraction (gateway becomes the only public entry).

---

## Full monorepo setup (three services)

Railway does not need a single multi-service `docker-compose` file. Create **three**
services from the **same** repo with different root / Dockerfile settings:

### 1. extraction

| Setting | Value |
|---------|--------|
| Root Directory | `.` (repo root) |
| Config as Code | `services/extraction/railway.toml` |
| Dockerfile | `services/extraction/Dockerfile` |
| Private networking | enabled (default) |

### 2. risk-engine

| Setting | Value |
|---------|--------|
| Root Directory | `services/risk-engine` |
| Config as Code | `services/risk-engine/railway.toml` |
| Dockerfile | `Dockerfile` (relative to root directory) |
| Private networking | enabled |

Deploy **after** extraction has successfully migrated Neon at least once. The
entrypoint retries process start **5 × 30s** if Hibernate `ddl-auto=validate` fails
(migrations not finished yet).

### 3. gateway

| Setting | Value |
|---------|--------|
| Root Directory | `.` (repo root) |
| Config as Code | `gateway/railway.toml` |
| Dockerfile | `gateway/Dockerfile` |
| Public domain | **yes** — this is the browser URL |

Set gateway upstream env vars to Railway **private** hosts (reference variables):

```text
EXTRACTION_UPSTREAM=${{extraction.RAILWAY_PRIVATE_DOMAIN}}:${{extraction.PORT}}
RISK_ENGINE_UPSTREAM=${{risk-engine.RAILWAY_PRIVATE_DOMAIN}}:${{risk-engine.PORT}}
```

(`PORT` on the right-hand side is the **target** service’s port, which Railway injects
per service. Gateway listens on its own `$PORT`.)

Nginx is rendered at boot from `gateway/nginx.conf.template` via `envsubst` so the
same image works in compose (`extraction:8000`) and on Railway (private DNS).

---

## Neon URL forms

Neon’s console connection string looks like:

```text
postgresql://USER:PASSWORD@HOST/DB?sslmode=require
```

Convert per service — **do not** paste the same string into both:

| Consumer | Env var | Form |
|----------|---------|------|
| extraction (SQLAlchemy + psycopg) | `DATABASE_URL` | `postgresql+psycopg://USER:PASSWORD@HOST/DB?sslmode=require` |
| risk-engine (JDBC) | `SPRING_DATASOURCE_URL` | `jdbc:postgresql://HOST/DB?sslmode=require` |
| risk-engine credentials | `SPRING_DATASOURCE_USERNAME` / `SPRING_DATASOURCE_PASSWORD` | Neon role + password |

Notes:

- Prefer Neon’s **direct** (non-pooler) host for migrations / long sessions if the
  pooler drops prepared statements; pooler is fine for many HTTP workloads.
- Enable **`vector`** (pgvector) on the Neon database before first migrate
  (`CREATE EXTENSION IF NOT EXISTS vector;` — also done by Alembic `001`).
- Never commit Neon credentials; rotate if they ever land in `.env` in a shared clone.

---

## Anthropic identity-linked API keys

If your `ANTHROPIC_API_KEY` is **identity-linked** (Anthropic console shows key type
**Personal**), every Claude request must include the workspace id header
`anthropic-workspace-id`. Without it, Anthropic returns HTTP 400.

**Where to find the workspace id:** In the [Anthropic Console](https://console.anthropic.com),
open **Settings → Workspace** (or the workspace switcher in the top bar). The workspace
id is shown in the workspace settings URL or details panel — copy the id string
(e.g. `ws_…` or similar) into Railway.

**Railway:** On the **extraction** service, set:

```text
ANTHROPIC_WORKSPACE_ID=<your-workspace-id>
```

The extraction service sends this on every `ChatAnthropic` call via
`default_headers`. Non-identity-linked keys can leave this unset.

---

## Environment variables (names only)

### extraction

| Name | Required | Notes |
|------|----------|--------|
| `DATABASE_URL` | yes | `postgresql+psycopg://…` Neon URL |
| `PORT` | set by Railway | uvicorn bind |
| `STORAGE_DIR` | yes | e.g. `/app/storage` (ephemeral on Railway) |
| `ANTHROPIC_API_KEY` | yes for real extract/seed | Claude extraction + Q&A |
| `ANTHROPIC_WORKSPACE_ID` | yes for identity-linked keys | Personal / identity-linked API keys require this header (see below) |
| `OPENAI_API_KEY` | optional | `text-embedding-3-small` for Q&A embeddings only |
| `JWT_SECRET` | yes | HS256 signing key |
| `DEMO_USER` | yes | seeded login |
| `DEMO_PASSWORD` | yes | seeded login |
| `EXTRACTION_MODEL` | no | default `claude-sonnet-4-6` |
| `EMBEDDING_MODEL` | no | default `text-embedding-3-small` |
| `MAX_CONTEXT_TOKENS` | no | default `12000` |
| `REVIEW_THRESHOLD` | no | default `0.7` |
| `QA_TOP_K` | no | |
| `QA_MIN_SIMILARITY` | no | |
| `CHUNK_TARGET_TOKENS` | no | |
| `CHUNK_OVERLAP_TOKENS` | no | |
| `RISK_CRITICAL_DAYS` | no | shared surface |
| `RISK_WARNING_DAYS` | no | |
| `SCHEDULE_DELAY_MS` | no | |

### risk-engine

| Name | Required | Notes |
|------|----------|--------|
| `SPRING_DATASOURCE_URL` | yes | `jdbc:postgresql://…` |
| `SPRING_DATASOURCE_USERNAME` | yes | |
| `SPRING_DATASOURCE_PASSWORD` | yes | |
| `PORT` | set by Railway | Spring `server.port` |
| `RISK_CRITICAL_DAYS` | no | default `90` |
| `RISK_WARNING_DAYS` | no | default `180` |
| `SCHEDULE_DELAY_MS` | no | default `300000` |
| `DB_VALIDATE_MAX_ATTEMPTS` | no | default `5` |
| `DB_VALIDATE_RETRY_DELAY_SEC` | no | default `30` |

### gateway

| Name | Required | Notes |
|------|----------|--------|
| `PORT` | set by Railway | nginx `listen` |
| `EXTRACTION_UPSTREAM` | yes | `host:port` (compose or Railway private) |
| `RISK_ENGINE_UPSTREAM` | yes | `host:port` |

Compose defaults (also in `.env.example`):

| Name | Local default |
|------|----------------|
| `EXTRACTION_UPSTREAM` | `extraction:8000` |
| `RISK_ENGINE_UPSTREAM` | `risk-engine:8081` |
| `PORT` (gateway) | `8080` |

---

## Boot / seed behavior (extraction)

On every start (`services/extraction/docker-entrypoint.sh`):

1. `alembic upgrade head`
2. `python -m app.db.seed` — idempotent demo user from `DEMO_USER` / `DEMO_PASSWORD`,
   then portfolio PDFs from `seed/pdfs/` **only if**:
   - `leases` table is empty, **and**
   - `ANTHROPIC_API_KEY` **and** `OPENAI_API_KEY` are set
3. `uvicorn` on `0.0.0.0:$PORT`

The Dockerfile **copies `seed/`** (including `seed/pdfs/`) into the image so first
boot on Railway can extract without an external volume. PDF storage under
`STORAGE_DIR` is ephemeral; seed re-ingests when the DB is empty.

---

## Redeploy

- Push to the connected branch, or **Railway → service → Redeploy**.
- Config-only changes (env vars): update variables → Redeploy that service.
- After changing Neon credentials, update **both** `DATABASE_URL` and
  `SPRING_DATASOURCE_*`, then redeploy extraction first, then risk-engine.
- Gateway redeploy when upstream private DNS/port references change.
- Schema changes: ship a new Alembic revision; extraction migrate-on-boot applies it;
  risk-engine `validate` + retry tolerates a short race.

Full-stack smoke (public gateway):

```bash
bash scripts/smoke.sh https://<gateway-public-host>
```

---

## Local parity

```bash
cp .env.example .env   # fill secrets locally; never commit .env
docker compose up --build
bash scripts/smoke.sh http://localhost:8080
```

---

## Config files in this repo

| File | Role |
|------|------|
| `railway.toml` | Default / first-deploy → extraction Dockerfile at repo root |
| `services/extraction/railway.toml` | Extraction service config-as-code |
| `services/risk-engine/railway.toml` | Risk-engine (root dir = that folder) |
| `gateway/railway.toml` | Gateway (root dir = repo root; set Config File path in UI) |
| `gateway/nginx.conf.template` | Upstream hosts via `EXTRACTION_UPSTREAM` / `RISK_ENGINE_UPSTREAM` / `PORT` |
