# Evaluation Report

**Generated:** 2026-08-31 19:45 UTC  
**Model(s):** claude-sonnet-4-6  
**Prompt version(s):** v1.0  
**Leases evaluated:** 1  
**Level:** 1 (extraction accuracy — offline / DB)  

## Summary

| Metric | Value |
|--------|-------|
| Overall field accuracy | 100.0% |
| Page-citation accuracy | 100.0% |
| Fields scored | 18 |
| Failures | 0 |

### Per-group accuracy

| Group | Accuracy |
|-------|----------|
| `parties_premises` | 100.0% |
| `term` | 100.0% |
| `financial` | 100.0% |
| `options_obligations` | 100.0% |
| `opex` | 100.0% |

## Confidence calibration

Headline artifact: predicted confidence bucket vs observed accuracy.

| Confidence bucket | N | Observed accuracy |
|-------------------|---|-------------------|
| 0.0–0.5 | 12 | 100.0% |
| 0.5–0.7 | 0 | n/a |
| 0.7–0.9 | 1 | 100.0% |
| 0.9–1.0 | 5 | 100.0% |

## Per-lease results

### `crowdstrike_capitol_tower_austin_lease` (crowdstrike_capitol_tower_austin_lease)

- lease_id: `7239318b-7c7d-4d9c-9d02-cae6733ec421`
- gold: `C:\Users\chmad\Downloads\projects\lease-intelligence-platform\services\extraction\evals\gold\crowdstrike_capitol_tower_austin_lease.json`
- overall: 100.0%
- page citation: 100.0%

| Field | Pass | Gold | Extracted | Gold page | Ext. page | Conf |
|-------|------|------|-----------|-----------|-----------|------|
| `landlord` | ✅ | 'EQC Capitol Tower Property LLC' | 'EQC Capitol Tower Property LLC' | 3 | 3 | 0.99 |
| `tenant` | ✅ | 'CrowdStrike, Inc.' | 'CrowdStrike, Inc.' | 3 | 3 | 0.99 |
| `premises_address` | ✅ | '206 East 9th Street, Austin, Texas (Suite 1400, 14th Floor)' | '206 East 9th Street, Austin, Texas (Suite 1400, 14th Floor)' | 3 | 3 | 0.30 |
| `rentable_sqft` | ✅ | 25805 | 25805 | 4 | 4 | 0.99 |
| `commencement_date` | ✅ | None | None | None | None | 0.00 |
| `expiration_date` | ✅ | None | None | None | None | 0.00 |
| `initial_term_months` | ✅ | 73 | 73 | 5 | 5 | 0.30 |
| `base_rent_schedule` | ✅ | [] | [] | None | None | 0.00 |
| `escalation_type` | ✅ | None | None | None | None | 0.00 |
| `escalation_value` | ✅ | None | None | None | None | 0.00 |
| `security_deposit` | ✅ | None | None | None | None | 0.00 |
| `renewal_options` | ✅ | [{'rent_basis': {'page': 44, 'value': 'Prevailing Market rate per rentable square foot for comparable space in the Bu... | [{'rent_basis': {'page': 44, 'value': 'Prevailing Market rate per rentable square foot for comparable space in the Bu... | None | None | 0.46 |
| `termination_option` | ✅ | None | None | None | None | 0.00 |
| `holdover_rate_pct` | ✅ | 150.0 | 150.0 | 22 | 22 | 0.30 |
| `cam_structure` | ✅ | 'base_year' | 'base_year' | 44 | 44 | 0.75 |
| `base_year` | ✅ | None | None | None | None | 0.00 |
| `cam_cap_pct` | ✅ | 5.0 | 5.0 | 34 | 34 | 0.95 |
| `cam_cap_type` | ✅ | 'cumulative, compounded' | 'cumulative, compounded' | 34 | 34 | 0.95 |

## Known failure cases

Auto-listed mismatches from this run (field, gold, extracted).

_None — all scored fields passed._

## Levels 2–3 (future)

Retrieval (Level 2) and generation faithfulness (Level 3) are **stubbed** — Q&A embeddings are currently disabled. See `evals/level2.py` and `evals/level3.py`.

## Analysis

<!-- BEGIN ANALYSIS -->
Add qualitative notes here. This section is preserved across `python -m evals.run` rewrites.

- What failed systematically?
- Prompt / routing changes to try next?
<!-- END ANALYSIS -->
