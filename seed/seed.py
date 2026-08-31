"""Portfolio seed CLI shim — production entrypoint is python -m app.db.seed."""

from __future__ import annotations

import logging

from app.db.seed import main

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
