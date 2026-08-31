# Design decisions log

Entries are appended per review session.

## D1. Process records live in docs/

Process records live in `docs/` (`docs/transcripts/`, `docs/PROMPT_LOG.md` at the end). Root `transcripts/` and `PROMPT_LOG.md` were deleted. `AGENTS.md` stays at root.

## D2. Two DB URL vars stay

Two DB URL vars stay: `DATABASE_URL` (SQLAlchemy) for extraction, `SPRING_DATASOURCE_URL` (JDBC) for risk-engine. No shared-var conversion.

## D3. web/package-lock.json is committed

`web/package-lock.json` is committed; all web build stages use `npm ci`.

## D4. Idempotency key

Idempotency key is `UNIQUE(document_id, prompt_version, model)`; `documents.sha256` uniqueness makes `document_id` a 1:1 content proxy. `AGENTS.md` §5 already corrected.

## D5. Seed runs on every container boot

Seed runs on every container boot; it is idempotent. Init-container is a production note for the README, not built here.

## D6. Enum-like columns stay plain strings

Enum-like columns (`documents.kind`, `obligations.kind`, `alerts.severity`/`status`) stay plain strings; values enforced in the app layer. `CHECK` constraints may be added later in the same migration that adds the ivfflat index.

## D7. base_rent_schedule shape

`base_rent_schedule` stays `list[BaseRentPeriod]` with per-row provenance; no parent `ExtractedValue` wrapper.

## D8. TerminationOption partial data

`TerminationOption` must allow partial data: sub-fields are `ExtractedValue` leaves whose `value` may be `None`.

## D9. cam_cap_type stays a free string

`cam_cap_type` stays a free string until real lease language is observed; TODO noted in `prompts/PROMPTS.md` changelog.

## D10. Injection-notice validation

Injection-notice validation runs on rendered output and the notice must live in template literal text, outside `{{ context }}`. Intentional.

## D11. PDF filesystem storage

PDFs stored on filesystem at `settings.STORAGE_DIR/<sha256>.pdf`; path derived from `document.sha256`, no new column. Ephemeral on Railway is an accepted demo tradeoff (seed re-ingests on boot); production = object storage.

## D12. Aggregate prompt_version

`prompt_version` stays a single aggregate version per full five-group pass.

## D13. Obligations delete-and-recreate

Obligations are delete-and-recreated per lease on persist; alert history for that lease is lost on re-extraction by design (deterministic beats diff/merge). README tradeoff.

## D14. Scanned pages in events

Scanned page numbers are reported in the `extraction.flagged` event payload, not persisted as schema.

## D15. LLM retry scope

LLM retry stays schema-validation-only; transient network retries are delegated to the SDK.

## D16. Q&A conversation history

Q&A conversation history is request-scoped only (client sends last N turns), never persisted — extraction stays stateless per golden rule 4.

## D17. Embedding provider and native dimension

**Provider:** OpenAI `text-embedding-3-small` via `langchain-openai` on `OPENAI_API_KEY`.

**Native dimension:** 1536 (`lease_chunks.embedding` is `vector(1536)` with no padding).

**Why not Anthropic / Voyage:** `langchain-anthropic` does not expose an embeddings class and Anthropic has no public embeddings API, so the Anthropic-first preference order falls through to OpenAI. Voyage was removed to avoid a second API key (`VOYAGE_API_KEY`) and zero-padding Voyage 1024-dim vectors into a 1536-dim column — padding distorts cosine similarity and complicates ops. Extraction LLM stays on `ANTHROPIC_API_KEY`; embeddings use a separate key we already expect in most stacks. Migration `003_embedding_openai_native` clears cached embeddings from the prior provider so re-extraction re-embeds at native dimension.
