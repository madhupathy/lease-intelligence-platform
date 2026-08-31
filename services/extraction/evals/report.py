"""EVAL_REPORT.md writer — preserves editable Analysis section across runs."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evals.level1 import CalibrationBucket, LeaseEvalResult, aggregate_group_accuracy, confidence_calibration

ANALYSIS_BEGIN = "<!-- BEGIN ANALYSIS -->"
ANALYSIS_END = "<!-- END ANALYSIS -->"
DEFAULT_ANALYSIS = """\
Add qualitative notes here. This section is preserved across `python -m evals.run` rewrites.

- What failed systematically?
- Prompt / routing changes to try next?
"""

REPO_ROOT = Path(__file__).resolve().parents[3]
REPORT_PATH = REPO_ROOT / "EVAL_REPORT.md"


def _extract_analysis(existing: str | None) -> str:
    if not existing:
        return DEFAULT_ANALYSIS
    match = re.search(
        re.escape(ANALYSIS_BEGIN) + r"(.*?)" + re.escape(ANALYSIS_END),
        existing,
        flags=re.DOTALL,
    )
    if not match:
        return DEFAULT_ANALYSIS
    body = match.group(1).strip("\n")
    return body if body.strip() else DEFAULT_ANALYSIS


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.1f}%"


def _fmt_val(value: Any) -> str:
    text = repr(value)
    if len(text) > 120:
        return text[:117] + "..."
    return text


def render_report(
    results: list[LeaseEvalResult],
    *,
    existing_report: str | None = None,
) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    models = sorted({r.model for r in results if r.model})
    prompts = sorted({r.prompt_version for r in results if r.prompt_version})
    all_fields = [f for r in results for f in r.field_results]
    overall = (
        sum(1 for f in all_fields if f.passed) / len(all_fields) if all_fields else 0.0
    )
    page_scored = [f for f in all_fields if f.page_match is not None]
    page_acc = (
        sum(1 for f in page_scored if f.page_match) / len(page_scored) if page_scored else None
    )
    group_acc = aggregate_group_accuracy(results)
    calibration = confidence_calibration(results)
    failures = [f for r in results for f in r.failures()]
    analysis = _extract_analysis(existing_report)

    lines: list[str] = [
        "# Evaluation Report",
        "",
        f"**Generated:** {now}  ",
        f"**Model(s):** {', '.join(models) or 'unknown'}  ",
        f"**Prompt version(s):** {', '.join(prompts) or 'unknown'}  ",
        f"**Leases evaluated:** {len(results)}  ",
        f"**Level:** 1 (extraction accuracy — offline / DB)  ",
        "",
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Overall field accuracy | {_fmt_pct(overall)} |",
        f"| Page-citation accuracy | {_fmt_pct(page_acc)} |",
        f"| Fields scored | {len(all_fields)} |",
        f"| Failures | {len(failures)} |",
        "",
        "### Per-group accuracy",
        "",
        "| Group | Accuracy |",
        "|-------|----------|",
    ]
    for group, acc in group_acc.items():
        lines.append(f"| `{group}` | {_fmt_pct(acc)} |")

    lines.extend(
        [
            "",
            "## Confidence calibration",
            "",
            "Headline artifact: predicted confidence bucket vs observed accuracy.",
            "",
            "| Confidence bucket | N | Observed accuracy |",
            "|-------------------|---|-------------------|",
        ]
    )
    for bucket in calibration:
        lines.append(
            f"| {bucket.label} | {bucket.count} | {_fmt_pct(bucket.accuracy)} |"
        )

    lines.extend(["", "## Per-lease results", ""])
    for lease in results:
        lines.append(f"### `{lease.pdf_stem}` ({lease.lease_name})")
        lines.append("")
        lines.append(f"- lease_id: `{lease.lease_id}`")
        lines.append(f"- gold: `{lease.gold_path}`")
        lines.append(f"- overall: {_fmt_pct(lease.overall_accuracy)}")
        lines.append(f"- page citation: {_fmt_pct(lease.page_citation_accuracy)}")
        lines.append("")
        lines.append("| Field | Pass | Gold | Extracted | Gold page | Ext. page | Conf |")
        lines.append("|-------|------|------|-----------|-----------|-----------|------|")
        for fr in lease.field_results:
            mark = "✅" if fr.passed else "❌"
            conf = f"{fr.confidence:.2f}" if fr.confidence is not None else "—"
            lines.append(
                f"| `{fr.field_key}` | {mark} | {_fmt_val(fr.gold_value)} | "
                f"{_fmt_val(fr.extracted_value)} | {fr.gold_page} | {fr.extracted_page} | {conf} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Known failure cases",
            "",
            "Auto-listed mismatches from this run (field, gold, extracted).",
            "",
        ]
    )
    if not failures:
        lines.append("_None — all scored fields passed._")
        lines.append("")
    else:
        lines.append("| Lease | Field | Gold | Extracted |")
        lines.append("|-------|-------|------|-----------|")
        for lease in results:
            for fr in lease.failures():
                lines.append(
                    f"| `{lease.pdf_stem}` | `{fr.field_key}` | "
                    f"{_fmt_val(fr.gold_value)} | {_fmt_val(fr.extracted_value)} |"
                )
        lines.append("")

    lines.extend(
        [
            "## Levels 2–3 (future)",
            "",
            "Retrieval (Level 2) and generation faithfulness (Level 3) are **stubbed** — "
            "Q&A embeddings are currently disabled. See `evals/level2.py` and `evals/level3.py`.",
            "",
            "## Analysis",
            "",
            ANALYSIS_BEGIN,
            analysis,
            ANALYSIS_END,
            "",
        ]
    )
    return "\n".join(lines)


def write_report(results: list[LeaseEvalResult], path: Path | None = None) -> Path:
    target = path or REPORT_PATH
    existing = target.read_text(encoding="utf-8") if target.exists() else None
    content = render_report(results, existing_report=existing)
    target.write_text(content, encoding="utf-8")
    return target
