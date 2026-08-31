"""Write a gold stub from a seeded lease's effective extraction.

Usage:
  cd services/extraction
  python -m evals.stub <lease_id>
"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

from sqlalchemy import select

from app.db.models import Document, Lease
from app.db.session import SessionLocal
from app.field_groups import FIELD_GROUPS
from evals.gold_io import GOLD_DIR, write_gold
from evals.level1 import load_effective_extraction


def _unwrap(field_value_json) -> object:
    if isinstance(field_value_json, dict) and "value" in field_value_json:
        return field_value_json.get("value")
    return field_value_json


def build_stub(lease_id: uuid.UUID) -> Path:
    with SessionLocal() as session:
        lease = session.get(Lease, lease_id)
        if lease is None:
            raise SystemExit(f"Lease not found: {lease_id}")

        by_key, _model, _prompt, _name = load_effective_extraction(session, lease_id)
        docs = session.scalars(
            select(Document).where(Document.lease_id == lease_id).order_by(Document.uploaded_at.asc())
        ).all()
        stem = Path(docs[0].filename).stem if docs else lease.name.replace(" ", "_").lower()

        fields: dict = {}
        for keys in FIELD_GROUPS.values():
            for key in keys:
                row = by_key.get(key)
                if row is None:
                    fields[key] = {"value": None, "page": None, "_verified": False}
                else:
                    fields[key] = {
                        "value": _unwrap(row.value_json),
                        "page": row.page,
                        "_verified": False,
                    }

        payload = {
            "pdf_stem": stem,
            "lease_id": str(lease_id),
            "lease_name": lease.name,
            "fields": fields,
        }

    out_path = GOLD_DIR / f"{stem}.json"
    write_gold(out_path, payload)
    return out_path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Write a gold stub from DB extraction")
    parser.add_argument("lease_id", help="Lease UUID to stub")
    args = parser.parse_args(argv)
    path = build_stub(uuid.UUID(args.lease_id))
    print(f"Wrote gold stub: {path}")
    print("Hand-correct values/pages, set _verified true, then run: python -m evals.run")


if __name__ == "__main__":
    main(sys.argv[1:])
