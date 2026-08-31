"""Evaluation runner — Level 1 offline extraction accuracy.

Usage:
  cd services/extraction
  python -m evals.run --all
  python -m evals.run --lease <uuid>
"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

from app.db.session import SessionLocal
from evals.gold_io import GOLD_DIR, list_gold_files, load_gold
from evals.level1 import (
    LeaseEvalResult,
    aggregate_group_accuracy,
    confidence_calibration,
    evaluate_lease,
    resolve_lease_for_gold,
)
from evals.level2 import note as level2_note
from evals.level3 import note as level3_note
from evals.report import write_report


def _print_table(results: list[LeaseEvalResult]) -> None:
    all_fields = [f for r in results for f in r.field_results]
    overall = (
        sum(1 for f in all_fields if f.passed) / len(all_fields) if all_fields else 0.0
    )
    page_scored = [f for f in all_fields if f.page_match is not None]
    page_acc = (
        sum(1 for f in page_scored if f.page_match) / len(page_scored) if page_scored else None
    )

    print()
    print("=" * 72)
    print("LEVEL 1 — Extraction eval (offline / DB)")
    print("=" * 72)
    print(f"Leases: {len(results)}  Fields: {len(all_fields)}")
    print(f"Overall accuracy:      {overall * 100:5.1f}%")
    if page_acc is not None:
        print(f"Page-citation accuracy:{page_acc * 100:5.1f}%")
    print()
    print("Per-group accuracy:")
    for group, acc in aggregate_group_accuracy(results).items():
        print(f"  {group:24s} {acc * 100:5.1f}%")
    print()
    print("Confidence calibration:")
    print(f"  {'bucket':12s} {'N':>5s}  {'obs.acc':>8s}")
    for bucket in confidence_calibration(results):
        acc = f"{bucket.accuracy * 100:5.1f}%" if bucket.accuracy is not None else "   n/a"
        print(f"  {bucket.label:12s} {bucket.count:5d}  {acc:>8s}")
    print()

    for lease in results:
        print("-" * 72)
        print(f"{lease.pdf_stem}  ({lease.lease_name})")
        print(f"  overall={lease.overall_accuracy * 100:.1f}%  model={lease.model}  prompt={lease.prompt_version}")
        for fr in lease.field_results:
            mark = "PASS" if fr.passed else "FAIL"
            print(f"  [{mark}] {fr.field_key}")
        fails = lease.failures()
        if fails:
            print(f"  failures: {', '.join(f.field_key for f in fails)}")
    print()
    print(level2_note())
    print(level3_note())


def _gold_for_lease(session, lease_id: uuid.UUID) -> Path | None:
    for path in list_gold_files():
        gold = load_gold(path)
        resolved = resolve_lease_for_gold(session, gold)
        if resolved == lease_id:
            return path
        if gold.get("lease_id") and uuid.UUID(str(gold["lease_id"])) == lease_id:
            return path
    return None


def run(*, lease_id: uuid.UUID | None = None, all_leases: bool = False) -> list[LeaseEvalResult]:
    results: list[LeaseEvalResult] = []
    with SessionLocal() as session:
        if lease_id is not None:
            gold_path = _gold_for_lease(session, lease_id)
            if gold_path is None:
                raise SystemExit(
                    f"No gold file for lease {lease_id}. "
                    f"Create one with: python -m evals.stub {lease_id}"
                )
            results.append(evaluate_lease(session, gold_path, lease_id=lease_id))
        elif all_leases:
            paths = list_gold_files()
            if not paths:
                raise SystemExit(
                    f"No gold JSON files in {GOLD_DIR}. "
                    "Add hand-labeled gold or run: python -m evals.stub <lease_id>"
                )
            for path in paths:
                results.append(evaluate_lease(session, path))
        else:
            # Default: all gold files present
            paths = list_gold_files()
            if not paths:
                raise SystemExit(
                    f"No gold JSON files in {GOLD_DIR}. "
                    "Add hand-labeled gold or run: python -m evals.stub <lease_id>"
                )
            for path in paths:
                results.append(evaluate_lease(session, path))
    return results


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run Level 1 extraction evaluation")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--lease", type=str, help="Evaluate a single lease UUID")
    group.add_argument("--all", action="store_true", help="Evaluate all gold files")
    args = parser.parse_args(argv)

    lease_uuid = uuid.UUID(args.lease) if args.lease else None
    results = run(lease_id=lease_uuid, all_leases=args.all or lease_uuid is None)
    _print_table(results)
    path = write_report(results)
    print(f"Wrote {path}")


if __name__ == "__main__":
    main(sys.argv[1:])
