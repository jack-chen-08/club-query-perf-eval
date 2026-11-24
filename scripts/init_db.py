"""Apply the schema and an index set to the benchmark database.

    python scripts/init_db.py                      # schema + baseline indexes
    python scripts/init_db.py --indexes sql/opt/010_indexes_optimized.sql
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys

import psycopg


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default=os.environ.get("DATABASE_URL"))
    ap.add_argument("--schema", default="sql/001_schema.sql")
    ap.add_argument("--indexes", default="sql/002_indexes_baseline.sql")
    args = ap.parse_args()
    if not args.dsn:
        print("DATABASE_URL is not set", file=sys.stderr)
        return 2

    with psycopg.connect(args.dsn, autocommit=True) as conn, conn.cursor() as cur:
        for path in [args.schema, args.indexes]:
            if path and os.path.exists(path):
                cur.execute(pathlib.Path(path).read_text(encoding="utf-8"))
                print("applied", path)
        cur.execute("ANALYZE")
        # VACUUM refreshes the visibility map so that the partial covering
        # indexes can actually serve index-only scans.
        cur.execute("VACUUM ANALYZE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
