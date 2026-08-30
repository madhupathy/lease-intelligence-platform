# Prompt log

Index of AI prompts used to build this repository, per the assignment's request to retain
prompts and commit history. Each row maps a build prompt to the commits it produced and the
exported chat transcript for that session.

Workflow: paste the prompt file into a fresh Cursor session → build → run the acceptance
checks → commit → export the chat ("Show Chat History" → "..." → "Export Chat") into
`transcripts/` → fill in the row below. Note any deviation from the prompt in the last
column — corrections and steering are part of the record, not something to hide.

| # | Prompt file | Session date | Commit(s) | Transcript | Outcome / deviations |
|---|-------------|--------------|-----------|------------|----------------------|
| 01 | [01-repo-skeleton.md](01-repo-skeleton.md) | | | transcripts/01-repo-skeleton.md | |
| 02 | [02-database-schema.md](02-database-schema.md) | | | transcripts/02-database-schema.md | |
| 03 | [03-extraction-schema-and-prompts.md](03-extraction-schema-and-prompts.md) | | | transcripts/03-extraction-schema-and-prompts.md | |
| 04 | [04-extraction-pipeline.md](04-extraction-pipeline.md) | | | transcripts/04-extraction-pipeline.md | |
| 05 | [05-ingestion-api-events.md](05-ingestion-api-events.md) | | | transcripts/05-ingestion-api-events.md | |
| 06 | [06-qa-rag.md](06-qa-rag.md) | | | transcripts/06-qa-rag.md | |
| 07 | [07-eval-harness.md](07-eval-harness.md) | | | transcripts/07-eval-harness.md | |
| 08 | [08-risk-engine-springboot.md](08-risk-engine-springboot.md) | | | transcripts/08-risk-engine-springboot.md | |
| 09 | [09-dashboard-react.md](09-dashboard-react.md) | | | transcripts/09-dashboard-react.md | |
| 10 | [10-gateway-jwt.md](10-gateway-jwt.md) | | | transcripts/10-gateway-jwt.md | |
| 11 | [11-deploy-railway.md](11-deploy-railway.md) | | | transcripts/11-deploy-railway.md | |
| 12 | [12-readme-polish.md](12-readme-polish.md) | | | transcripts/12-readme-polish.md | |

Ad-hoc sessions (debugging, tuning, anything outside the numbered sequence) get their own
rows appended below, with transcript files named `adhoc-YYYYMMDD-topic.md`.

| Date | Topic | Commit(s) | Transcript | Notes |
|------|-------|-----------|------------|-------|
| | | | | |

Conventions:
- One Cursor session per prompt; fresh context each time.
- Every prompt pasted into Cursor ends with: "Report all files created or changed and any
  open questions. Do not commit. Stop after implementation so I can review first."
- Transcripts are committed unedited. Runtime LLM prompt templates (the ones the deployed
  system uses) live separately in `services/extraction/prompts/` and are versioned there.
