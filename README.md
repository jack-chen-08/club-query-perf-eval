# club-query-perf-eval

多会所会员空间 · 查询性能测评（票据 #2449）。

一个可复现的 PostgreSQL 测评工程：固定种子生成虚构的多会所会员数据，跑 10 条列表/驾驶舱
查询，记录 `EXPLAIN (ANALYZE, BUFFERS)`，对索引与 SQL 改写做前后实测。

A reproducible PostgreSQL performance evaluation for a multi-club member platform:
deterministic fictional data, ten list/dashboard queries, `EXPLAIN (ANALYZE, BUFFERS)`
snapshots, and measured before/after optimizations.

## 结论摘要 / TL;DR

* 10 会所（3,000 企业 / 30,000 联系人 / 200,000 报名 / 500,000 SOP 步骤）下，
  **10 条查询全部达标**：会所内 p95 最差 43 ms（目标 200 ms），跨会所聚合最差 45 ms
  （目标 2,000 ms）；冷缓存首跑最差 52 ms。
* 没有一条“未达标”可补，于是对全部 10 条都给了索引/改写方案并实测：9 条显著提速
  （1.3×–55×），d04 例外——跨会所漏斗业务上就是读全表，45 ms 由 5 万行决定，
  正确处置是缓存/物化视图而非加索引。
* 索引价值不在把 43 ms 变 0.8 ms，而在消除“缓存一冷就退化成全表扫描”的风险：
  q04 冷热差由 7 ms 压到 0.3 ms。

完整数据、逐条瓶颈与冷热对比见 [REPORT.md](REPORT.md)。

## 目录结构 / Layout

```text
sql/001_schema.sql                 表结构（软删除、org_id/site_id、金额以分存储）
sql/002_indexes_baseline.sql       基线：仅主键与自然键（上游票据交付时的状态）
sql/queries/q01..q05,d01..d05.sql  10 条待测查询
sql/opt/010_indexes_optimized.sql  优化索引层（12 个部分索引 + pg_trgm）
sql/opt/queries/                   2 处 SQL 改写（d02 EXISTS、d03 LATERAL、d05 预聚合）
scripts/gen_data.py                确定性数据生成器（默认 seed=42）
scripts/init_db.py                 建表 / 装索引 / ANALYZE + VACUUM
scripts/bench.py                   热缓存基准，100 次/条，p50/p95 + EXPLAIN 落盘
scripts/cold_bench.py              冷缓存基准，查前 docker restart，计首跑耗时
scripts/check_seed.py              同 seed 双库生成，比对行数与 id 校验和
scripts/make_report.py             由 EVIDENCE/*.json 生成 REPORT.md
EVIDENCE/                          原始证据：EXPLAIN 文本/JSON、两轮结果、确定性核对
```

## 快速开始 / Quickstart

```bash
docker run -d --name cm2449-pg -e POSTGRES_DB=bench -p 55433:5432 postgres:16
python3 -m venv .venv && .venv/bin/pip install 'psycopg[binary]==3.2.3'
export DATABASE_URL=postgresql://postgres@127.0.0.1:55433/bench

.venv/bin/python scripts/init_db.py
.venv/bin/python scripts/gen_data.py --clubs 10 --seed 42
.venv/bin/python scripts/bench.py --label baseline --runs 100 --out EVIDENCE/baseline/10clubs
.venv/bin/python scripts/cold_bench.py --label cold_baseline --out EVIDENCE/cold/baseline_10clubs
```

（上面用的是免密本地连接；生产/远程库请自备 DSN，不要提交 `.env`。）

## 数据说明 / About the data

全部为虚构数据：企业名由音节池拼合（星海科技一类），联系人姓名、手机号、邮箱均为
`13x…` / `example.invalid` 形式的占位值，不含任何真实企业或个人信息。

时间轴默认锚定在“当天回溯 1080 天”，便于 `now() - interval '365 days'` 这类窗口有数据；
行数与 id 只由 `--seed` 决定，需要绝对固定的时间戳可设 `GEN_ANCHOR=2026-11-01`。

## 已知局限 / Limits

* 单机单库、单会话只读测量，未做多会话并发下的 p95。
* 规模到 10 会所为设计上限；再往上 d04/d05 先破线，处置顺序是物化视图 → 预聚合日表。
* 未做计划漂移回归；建议把 `EVIDENCE/*/q*.explain.txt` 纳入 CI 比对。
