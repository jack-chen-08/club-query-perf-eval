"""Cold-cache benchmark: restart PostgreSQL before each query, then time the very
first execution (nothing is in shared_buffers), then run the warm repetitions.

Why: on a fast NVMe host every query already meets its target with a warm cache,
so the interesting question "which query depends on the cache?" is answered by a
cold reference point. After the restart, each query is executed once, timed, and
only then EXPLAINed and repeated.

    python scripts/cold_bench.py --label cold_baseline --runs 5 --out EVIDENCE/cold/baseline_10clubs
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import statistics
import subprocess
import sys
import time

import psycopg

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from bench import CLUB_FILTERED, QUERIES, build_params, resolve_sql, _node_types, _plain  # noqa: E402


def wait_ready(dsn: str, timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            with psycopg.connect(dsn, connect_timeout=2) as c:
                c.execute("SELECT 1").fetchone()
                return
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(0.4)
    raise RuntimeError(f"postgres not ready: {last}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default=os.environ.get("DATABASE_URL"))
    ap.add_argument("--label", required=True)
    ap.add_argument("--runs", type=int, default=5, help="warm repetitions AFTER the cold run")
    ap.add_argument("--out", required=True)
    ap.add_argument("--restart-cmd", default="docker restart cm2449-pg")
    ap.add_argument("--settle", type=float, default=1.5, help="seconds to wait after readiness")
    ap.add_argument("--only", default="", help="comma separated query ids")
    ap.add_argument("--overlay", default="", help="directory with rewritten SQL files")
    args = ap.parse_args()
    if not args.dsn:
        print("DATABASE_URL is not set")
        return 2

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    wanted = set(args.only.split(",")) if args.only else None
    results = {"label": args.label, "warm_runs": args.runs, "queries": {}}
    root = pathlib.Path(".")

    with psycopg.connect(args.dsn, autocommit=True) as conn, conn.cursor() as cur:
        params = build_params(cur)
        results["clubs"] = cur.execute("SELECT count(*) FROM clubs").fetchone()[0]

    for qid, path, cn in QUERIES:
        if wanted and qid not in wanted:
            continue
        subprocess.run(args.restart_cmd, shell=True, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        wait_ready(args.dsn)
        time.sleep(args.settle)

        sql = resolve_sql(root, args.overlay, path)
        with psycopg.connect(args.dsn, autocommit=True) as conn, conn.cursor() as cur:
            t0 = time.perf_counter()
            cur.execute(sql, params)
            rows = len(cur.fetchall())
            cold_ms = (time.perf_counter() - t0) * 1000.0

            plan = cur.execute(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {sql}", params).fetchone()[0][0]
            (out / f"{qid}.explain.txt").write_text(_plain(cur, sql, params), encoding="utf-8")

            warm = []
            for _ in range(args.runs):
                t = time.perf_counter()
                cur.execute(sql, params)
                cur.fetchall()
                warm.append((time.perf_counter() - t) * 1000.0)

        target = 200.0 if qid in CLUB_FILTERED else 2000.0
        results["queries"][qid] = {
            "title": cn,
            "cold_ms": round(cold_ms, 3),
            "warm_median_ms": round(statistics.median(warm), 3),
            "rows": rows,
            "target_ms": target,
            "pass": cold_ms < target,
            "plan_nodes": _node_types(plan["Plan"]),
            "shared_hit": plan["Plan"].get("Shared Hit Blocks"),
            "shared_read": plan["Plan"].get("Shared Read Blocks"),
        }
        print(f"{qid} cold={cold_ms:9.2f}ms target={target:6.0f}ms "
              f"{'PASS' if cold_ms < target else 'FAIL'} rows={rows}")

    name = args.only.replace(",", "_") if args.only else "all"
    (out / f"results_{name}.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
