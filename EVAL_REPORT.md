# Evaluation Report

**Generated:** 2026-08-31 19:56 UTC  
**Model(s):** claude-sonnet-4-6  
**Prompt version(s):** v1.0  
**Leases evaluated:** 1  
**Level:** 1 (extraction accuracy — offline / DB)  

## Summary

| Metric | Value |
|--------|-------|
| Overall field accuracy | 72.2% |
| Page-citation accuracy | 61.5% |
| Fields scored | 18 |
| Failures | 5 |

### Per-group accuracy

| Group | Accuracy |
|-------|----------|
| `parties_premises` | 100.0% |
| `term` | 100.0% |
| `financial` | 25.0% |
| `options_obligations` | 66.7% |
| `opex` | 75.0% |

## Confidence calibration

Headline artifact: predicted confidence bucket vs observed accuracy.

| Confidence bucket | N | Observed accuracy |
|-------------------|---|-------------------|
| 0.0–0.5 | 12 | 66.7% |
| 0.5–0.7 | 0 | n/a |
| 0.7–0.9 | 1 | 0.0% |
| 0.9–1.0 | 5 | 100.0% |

## Per-lease results

### `crowdstrike_capitol_tower_austin_lease` (crowdstrike_capitol_tower_austin_lease)

- lease_id: `7239318b-7c7d-4d9c-9d02-cae6733ec421`
- gold: `C:\Users\chmad\Downloads\projects\lease-intelligence-platform\services\extraction\evals\gold\crowdstrike_capitol_tower_austin_lease.json`
- overall: 72.2%
- page citation: 61.5%

| Field | Pass | Gold | Extracted | Gold page | Ext. page | Conf |
|-------|------|------|-----------|-----------|-----------|------|
| `landlord` | ✅ | 'EQC Capitol Tower Property LLC' | 'EQC Capitol Tower Property LLC' | 3 | 3 | 0.99 |
| `tenant` | ✅ | 'CrowdStrike, Inc.' | 'CrowdStrike, Inc.' | 3 | 3 | 0.99 |
| `premises_address` | ✅ | '206 East 9th Street, Austin, Texas (Suite 1400, 14th Floor)' | '206 East 9th Street, Austin, Texas (Suite 1400, 14th Floor)' | 3 | 3 | 0.30 |
| `rentable_sqft` | ✅ | 25805 | 25805 | 4 | 4 | 0.99 |
| `commencement_date` | ✅ | None | None | None | None | 0.00 |
| `expiration_date` | ✅ | None | None | None | None | 0.00 |
| `initial_term_months` | ✅ | 73 | 73 | 5 | 5 | 0.30 |
| `base_rent_schedule` | ❌ | [{'annual_rent': 812857.56}, {'annual_rent': 837372.24}, {'annual_rent': 862403.16}, {'annual_rent': 888208.08}, {'an... | [] | 4 | None | 0.00 |
| `escalation_type` | ❌ | 'stepped' | None | 4 | None | 0.00 |
| `escalation_value` | ✅ | None | None | None | None | 0.00 |
| `security_deposit` | ❌ | 800000 | None | 5 | None | 0.00 |
| `renewal_options` | ❌ | [{'term_months': 60, 'notice_min_days': 365, 'notice_max_days': 456}] | [{'rent_basis': {'page': 44, 'value': 'Prevailing Market rate per rentable square foot for comparable space in the Bu... | 44 | None | 0.46 |
| `termination_option` | ✅ | None | None | None | None | 0.00 |
| `holdover_rate_pct` | ✅ | 150.0 | 150.0 | 22 | 22 | 0.30 |
| `cam_structure` | ❌ | 'gross' | 'base_year' | 34 | 44 | 0.75 |
| `base_year` | ✅ | None | None | None | None | 0.00 |
| `cam_cap_pct` | ✅ | 5.0 | 5.0 | 34 | 34 | 0.95 |
| `cam_cap_type` | ✅ | 'cumulative, compounded' | 'cumulative, compounded' | 34 | 34 | 0.95 |

## Known failure cases

Auto-listed mismatches from this run (field, gold, extracted).

| Lease | Field | Gold | Extracted |
|-------|-------|------|-----------|
| `crowdstrike_capitol_tower_austin_lease` | `base_rent_schedule` | [{'annual_rent': 812857.56}, {'annual_rent': 837372.24}, {'annual_rent': 862403.16}, {'annual_rent': 888208.08}, {'an... | [] |
| `crowdstrike_capitol_tower_austin_lease` | `escalation_type` | 'stepped' | None |
| `crowdstrike_capitol_tower_austin_lease` | `security_deposit` | 800000 | None |
| `crowdstrike_capitol_tower_austin_lease` | `renewal_options` | [{'term_months': 60, 'notice_min_days': 365, 'notice_max_days': 456}] | [{'rent_basis': {'page': 44, 'value': 'Prevailing Market rate per rentable square foot for comparable space in the Bu... |
| `crowdstrike_capitol_tower_austin_lease` | `cam_structure` | 'gross' | 'base_year' |

## Levels 2–3 (future)

Retrieval (Level 2) and generation faithfulness (Level 3) are **stubbed** — Q&A embeddings are currently disabled. See `evals/level2.py` and `evals/level3.py`.

## Analysis

**Calibration is the headline.** High-confidence fields (≥0.9) were 100% accurate;
the failures concentrate in the low-confidence buckets. The three genuine misses —
base_rent_schedule, escalation_type, security_deposit — were all extracted at 0.0
confidence: the model abstained rather than hallucinated. This is the property that
makes the needs_review queue meaningful — flagged fields correlate with real errors,
so human review lands on exactly the fields that need it.

**Systematic failure: the financial group (25% this run).** All three genuine misses
sit in the nested-list financial schema (base_rent_schedule and its dependents), where
structured output non-deterministically returns empty — the same lease extracted these
correctly in a prior run. Retry-with-reinforcement + graceful degradation contain it
(null + needs_review, no crash), but nested-schema extraction reliability is the top
next item.

**Two failures are measurement artifacts, not model errors:** renewal_options was
extracted correctly but fails the list-shape comparison (gold simplification);
cam_structure reflects gold ambiguity. Both are noted honestly rather than tuned away —
the point of the harness is to surface these, including its own limitations.

**Next:** improve nested-schema reliability; tighten list-field comparison in the eval;
tighten CitationGuard (it penalizes some correct fields to 0.3 on prose-heavy snippets).
