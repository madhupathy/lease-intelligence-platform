# Evaluation Report

**Generated:** (not yet run)  
**Model(s):** —  
**Prompt version(s):** —  
**Leases evaluated:** 0  
**Level:** 1 (extraction accuracy — offline / DB)  

## Summary

No Level 1 run yet. After labeling gold stubs:

```bash
cd services/extraction
python -m evals.stub <lease_id>   # pre-fill from DB
# hand-correct gold/*.json, set _verified true
python -m evals.run --all
```

## Confidence calibration

Headline artifact appears after the first `python -m evals.run`.

## Levels 2–3 (future)

Retrieval (Level 2) and generation faithfulness (Level 3) are **stubbed** — Q&A embeddings are currently disabled.

## Analysis

<!-- BEGIN ANALYSIS -->
Add qualitative notes here. This section is preserved across `python -m evals.run` rewrites.

- What failed systematically?
- Prompt / routing changes to try next?
<!-- END ANALYSIS -->
