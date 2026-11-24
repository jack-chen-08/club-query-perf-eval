"""Benchmark the ten evaluation queries and capture EXPLAIN (ANALYZE, BUFFERS).

For every query the script
  1. runs EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) and stores the plan,
  2. times N executions individually and reports p50 / p95 / max.

Targets from the ticket: club-filtered queries p95 < 200 ms, cross-club
aggregates < 2 s.

Usage:
    export DATABASE_URL=postgresql://postgres:***@127.0.0.1:55433/bench
    python scripts/bench.py --label baseline_10clubs --runs 100 --out EVIDENCE/baseline/10clubs
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import statistics
import time

import psycopg

NS = "6f9619ff-8b86-d011-b42d-00c04fc964ff"
CLUB_FILTERED = {"q01", "q02", "q03", "q04", "q05", "d01", "d02", "d03"}
QUERIES = [
    ("q01", "sql/queries/q01_enterprise_list.sql", "会员企业列表筛选"),
    ("q02", "sql/queries/q02_contact_search.sql", "联系人关键词搜索"),
    ("q03", "sql/queries/q03_event_roster.sql", "活动报名名单"),
    ("q04", "sql/queries/q04_sop_todo.sql", "SOP 待办列表"),
    ("q05", "sql/queries/q05_opportunity_kanban.sql", "商机看板分组计数"),
    ("d01", "sql/queries/d01_new_enterprises_monthly.sql", "驾驶舱·月度新增会员"),
    ("d02", "sql/queries/d02_active_member_ratio.sql", "驾驶舱·活跃会员占比"),
    ("d03", "sql/queries/d03_event_fill_rate.sql", "驾驶舱·活动平均上座率"),
    ("d04", "sql/queries/d04_pipeline_by_stage_all_clubs.sql", "驾驶舱·跨会所商机漏斗"),
    ("d05", "sql/queries/d05_top_enterprises.sql", "驾驶舱·跨会所报名 TOP10"),
]


def club_key(index: int) -> str:
    import uuid
    return str(uuid.uuid5(uuid.UUID(NS), f"club:{index}"))


def event_key(club_index: int, event_index: int) -> str:
    import uuid
    return str(uuid.uuid5(uuid.UUID(NS), f"ev:{club_index * 10000 + event_index}"))


def build_params(cur) -> dict:
    cur.execute("SELECT industry, status FROM enterprises WHERE club_id = %s LIMIT 1", (club_key(0),))
    industry, status = cur.fetchone()
    return {
        "club_id": club_key(0),
        "industry": industry,
        "status": status,
        "kw_like": "%138%",
        "event_id": event_key(0, 7),
    }


def resolve_sql(root: pathlib.Path, overlay: str, relpath: str) -> str:
    """Return the SQL text, preferring a rewritten file in the overlay directory."""
    if overlay:
        cand = pathlib.Path(overlay) / pathlib.Path(relpath).name
        if cand.exists():
            return cand.read_text(encoding="utf-8")
    return (root / relpath).read_text(encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default=os.environ.get("DATABASE_URL"))
    ap.add_argument("--label", required=True)
    ap.add_argument("--runs", type=int, default=100)
    ap.add_argument("--out", required=True)
    ap.add_argument("--queries-dir", default=".")
    ap.add_argument("--overlay", default="", help="directory with rewritten SQL files, same basenames")
    args = ap.parse_args()
    if not args.dsn:
        print("DATABASE_URL is not set")
        return 2

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    root = pathlib.Path(args.queries_dir)
    results = {"label": args.label, "runs": args.runs, "queries": {}}

    with psycopg.connect(args.dsn, autocommit=True) as conn, conn.cursor() as cur:
        params = build_params(cur)
        cur.execute("SELECT count(*) FROM clubs")
        club_count = cur.fetchone()[0]
        results["clubs"] = club_count

        for qid, path, cn in QUERIES:
            sql = resolve_sql(root, args.overlay, path)
            plan = cur.execute(
                f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {sql}", params).fetchone()[0][0]
            (out / f"{qid}.explain.json").write_text(
                json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
            (out / f"{qid}.explain.txt").write_text(
                _plain(cur, sql, params), encoding="utf-8")

            timings = []
            rows = 0
            for _ in range(args.runs):
                t0 = time.perf_counter()
                cur.execute(sql, params)
                rows = len(cur.fetchall())
                timings.append((time.perf_counter() - t0) * 1000.0)

            p50 = statistics.median(timings)
            p95 = statistics.quantiles(timings, n=20)[-1] if len(timings) > 1 else timings[0]
            target = 200.0 if qid in CLUB_FILTERED else 2000.0
            results["queries"][qid] = {
                "title": cn,
                "snapshot_ms": round(plan["Execution Time"], 3),
                "p50_ms": round(p50, 3),
                "p95_ms": round(p95, 3),
                "max_ms": round(max(timings), 3),
                "rows": rows,
                "target_ms": target,
                "pass": p95 < target,
                "plan_nodes": _node_types(plan["Plan"]),
            }
            print(f"{qid} p95={p95:8.2f}ms target={target:6.0f}ms "
                  f"{'PASS' if p95 < target else 'FAIL'} rows={rows}")

    (out / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "results.md").write_text(_markdown(results), encoding="utf-8")
    return 0


def _plain(cur, sql: str, params: dict) -> str:
    rows = cur.execute(f"EXPLAIN (ANALYZE, BUFFERS) {sql}", params).fetchall()
    return "\n".join(r[0] for r in rows) + "\n"


def _node_types(node, acc=None):
    acc = acc if acc is not None else []
    acc.append(node.get("Node Type"))
    for ch in node.get("Plans", []) or []:
        _node_types(ch, acc)
    return acc


def _markdown(r: dict) -> str:
    lines = [f"# Benchmark {r['label']}", "",
             f"clubs={r['clubs']}  runs per query={r['runs']}", "",
             "| Query | 名称 | p50 ms | p95 ms | target ms | snapshot (EXPLAIN ANALYZE) | rows | 结果 |",
             "|:--|:--|--:|--:|--:|--:|--:|:--|"]
    for qid, v in r["queries"].items():
        lines.append(f"| {qid} | {v['title']} | {v['p50_ms']} | {v['p95_ms']} | {v['target_ms']:.0f} | "
                     f"{v['snapshot_ms']} | {v['rows']} | {'PASS' if v['pass'] else '**FAIL**'} |")
    bad = [q for q, v in r["queries"].items() if not v["pass"]]
    lines += ["", f"未达标：{', '.join(bad) if bad else '无'}", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
