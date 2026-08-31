"""Tests for EVAL_REPORT.md Analysis section preservation."""

from evals.report import ANALYSIS_BEGIN, ANALYSIS_END, render_report
from evals.level1 import FieldResult, LeaseEvalResult


def test_analysis_preserved_across_render():
    existing = f"""# Evaluation Report

## Analysis

{ANALYSIS_BEGIN}
Custom note: renewal notice windows look soft.
{ANALYSIS_END}
"""
    lease = LeaseEvalResult(
        lease_id="00000000-0000-0000-0000-000000000001",
        lease_name="Demo",
        pdf_stem="demo",
        gold_path="evals/gold/demo.json",
        field_results=[
            FieldResult(
                field_key="landlord",
                group="parties_premises",
                passed=True,
                gold_value="A",
                extracted_value="A",
                gold_page=1,
                extracted_page=1,
                page_match=True,
                confidence=0.95,
            )
        ],
        model="claude-sonnet-4-6",
        prompt_version="1.0",
    )
    out = render_report([lease], existing_report=existing)
    assert "Custom note: renewal notice windows look soft." in out
    assert ANALYSIS_BEGIN in out and ANALYSIS_END in out
