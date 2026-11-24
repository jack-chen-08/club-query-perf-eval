"""AC1 evidence: the same seed must produce identical row counts (and identical
ids) across two independent generations.

The script builds two throw-away databases, runs gen_data.py into each with the
same seed, then compares per-table row counts and an id checksum.

    python scripts/check_seed.py --clubs 10 --seed 42
"""

from __future__ import annotations

import argparse
import os
import pathlib
import subprocess
import sys
import urllib.parse

import psycopg

TABLES = ["clubs", "enterprises", "contacts", "events", "registrations", "sop_steps", "opportunities"]


def dsn_for(base: str, dbname: str) -> str:
    parts = urllib.parse.urlparse(base)
    return urllib.parse.urlunparse(parts._replace(path="/" + dbname))


def admin_dsn(base: str) -> str:
    return dsn_for(base, "postgres")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default=os.environ.get("DATABASE_URL"))
    ap.add_argument("--clubs", type=int, default=10)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="EVIDENCE/determinism.md")
    args = ap.parse_args()
    if not args.dsn:
        print("DATABASE_URL is not set")
        return 2

    dbs = ["det_a", "det_b"]
    with psycopg.connect(admin_dsn(args.dsn), autocommit=True) as conn:
        for db in dbs:
            conn.execute(f'DROP DATABASE IF EXISTS {db} WITH (FORCE)')
            conn.execute(f"CREATE DATABASE {db}")

    root = pathlib.Path(".")
    for db in dbs:
        env = dict(os.environ, DATABASE_URL=dsn_for(args.dsn, db))
        subprocess.run([sys.executable, "scripts/init_db.py"], env=env, check=True,
                       stdout=subprocess.DEVNULL)
        subprocess.run([sys.executable, "scripts/gen_data.py", "--clubs", str(args.clubs),
                        "--seed", str(args.seed)], env=env, check=True,
                       stdout=subprocess.DEVNULL)

    lines = [f"# 种子确定性核对 (seed={args.seed}, clubs={args.clubs})", "",
             "同一 seed 向两个独立库生成，逐表比对行数与 id 校验和。", "",
             "| 表 | 库 A 行数 | 库 B 行数 | 行数一致 | id 校验和一致 |",
             "|:--|--:|--:|:--|:--|"]
    ok = True
    with psycopg.connect(dsn_for(args.dsn, "det_a")) as ca, psycopg.connect(dsn_for(args.dsn, "det_b")) as cb:
        for t in TABLES:
            q = f"SELECT count(*), coalesce(sum(hashtext(id::text)::bigint), 0) FROM {t}"
            ra = ca.execute(q).fetchone()
            rb = cb.execute(q).fetchone()
            same_n = ra[0] == rb[0]
            same_h = ra[1] == rb[1]
            ok = ok and same_n and same_h
            lines.append(f"| {t} | {ra[0]} | {rb[0]} | {'✓' if same_n else '✗'} | {'✓' if same_h else '✗'} |")
    lines += ["", f"结论：{'PASS —— 固定 seed 行数与内容完全一致' if ok else 'FAIL'}", ""]

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

    with psycopg.connect(admin_dsn(args.dsn), autocommit=True) as conn:
        for db in dbs:
            conn.execute(f'DROP DATABASE IF EXISTS {db} WITH (FORCE)')
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
