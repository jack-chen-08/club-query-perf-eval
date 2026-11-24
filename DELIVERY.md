# 交付说明 · 多会所会员空间查询性能测评（#2449）

| 项 | 内容 |
| --- | --- |
| 交付物 | 可复现的测评工程（生成器 + 10 条查询 + EXPLAIN 原始记录 + 优化层 + 报告），含 git 历史 |
| 目录 | `2449_club_query_perf/`（仓库名建议 `club-query-perf-eval`） |
| 数据库 | PostgreSQL 16.16（Docker 容器 `cm2449-pg`，宿主 55433，库体积 192 MB） |
| 实测规模 | 1 会所 / 10 会所两档；10 会所 = 3,000 企业、30,000 联系人、6,000 活动、200,000 报名、500,000 SOP 步骤、50,000 商机 |
| 主报告 | `REPORT.md`（含冷热两套实测与逐条优化前后对比） |
| 原始证据 | `EVIDENCE/`（每条查询的 EXPLAIN TEXT + JSON，两档规模、基线与优化后各一套） |
| 结论 | 10 会所下 10 条查询全部达标；9 条经索引/改写提速 1.3×–55×，d04 无提速并说明原因 |

---

## 1. 验收条件对照

| AC | 要求 | 证据 | 状态 |
| --- | --- | --- | --- |
| ① | 生成器固定 seed=42，同一 seed 下公司数与联系人数完全一致 | `scripts/gen_data.py`；`scripts/check_seed.py` 双库生成比对；`EVIDENCE/determinism.md`（七张表行数与 id 校验和全一致） | 满足 |
| ② | 10 条查询（5 列表/详情 + 5 驾驶舱），单会所 P95 < 200 ms、跨会所聚合 < 2 s，附 1 与 10 会所的 EXPLAIN | `sql/queries/q01..q05,d01..d05.sql`；`bench.py` 100 次/条计时；`EVIDENCE/baseline/1club/`、`EVIDENCE/baseline/10clubs/` 各 10 份 EXPLAIN TEXT+JSON | 满足 |
| ③ | 对未达标查询给出索引或改写建议，附优化前后实测 | 本规模**无一条未达标**（最差 q04 43 ms/200 ms，d04 45 ms/2,000 ms）；仍对全部 10 条给出方案并实测，见 `REPORT.md` §9 与 `sql/opt/` | 满足（无未达标项，故对全量给方案） |
| ④ | 统一约定：UUID 主键、org_id/site_id、created_at/created_by/updated_at/deleted_at、软删除、金额以分 | `sql/001_schema.sql` 每张表均含上述列；`amount_cents bigint`；所有列表/指标查询带 `deleted_at IS NULL` | 满足 |

## 2. 关键实测数字（10 会所）

| 查询 | 基线 p95 | 优化后 p95 | 提升 | 冷缓存首跑（基→优化） |
| --- | ---: | ---: | ---: | --- |
| q01 企业列表筛选 | 0.80 ms | 0.58 ms | 1.4× | 3.8 → 2.6 ms |
| q02 联系人关键词搜索 | 8.39 ms | 1.65 ms | 5.1× | 25.8 → 4.9 ms |
| q03 活动报名名单 | 19.74 ms | 1.42 ms | 13.9× | 28.2 → 5.7 ms |
| q04 SOP 待办 | 43.49 ms | 0.76 ms | 57× | 50.3 → 3.1 ms |
| q05 商机看板分组 | 6.83 ms | 1.25 ms | 5.5× | 20.9 → 3.2 ms |
| d01 月度新增会员 | 0.86 ms | 0.54 ms | 1.6× | 3.3 → 2.5 ms |
| d02 活跃会员占比 | 20.68 ms | 1.97 ms | 10.5× | 20.4 → 10.1 ms |
| d03 活动上座率 | 32.84 ms | 1.53 ms | 21.5× | 40.0 → 7.3 ms |
| d04 跨会所商机漏斗 | 44.91 ms | 46.36 ms | 0.97×（无提速） | 52.7 → 58.5 ms |
| d05 跨会所报名 TOP10 | 36.92 ms | 11.93 ms | 3.1× | 32.2 → 16.5 ms |

## 3. 为什么没有“未达标”还给了优化

票据设想的是“跑出慢查询再优化”。实测下来本数据量在 NVMe 上不构成压力，最慢 50 ms。
为不把“全过”当成结论糊过去，做了两件事：

1. 增加**冷缓存**测量（每条查询前 `docker restart`，清空 shared_buffers 后计首跑），
   这是单查询最坏的真实条件；结果最差 52 ms，仍全过。
2. 对全部 10 条给索引/改写并实测，把“有没有余量、余量来自哪儿”摊开；
   d04 明确报告为**无提速**并说明它业务上就是读全表，处置应是物化视图而不是加索引。

## 4. 交付清单

| 路径 | 说明 |
| --- | --- |
| `REPORT.md` | 主报告：环境、规模、方法、基线/优化、冷热对比、局限 |
| `README.md` | 工程说明与复现步骤（中英对照摘要） |
| `sql/001_schema.sql` | 7 张表，统一审计列与软删除，金额以分 |
| `sql/002_indexes_baseline.sql` | 基线索引（仅主键与自然键，模拟上游交付态） |
| `sql/queries/q01..q05,d01..d05.sql` | 10 条待测查询，参数化 |
| `sql/opt/010_indexes_optimized.sql` | 12 个部分索引 + pg_trgm |
| `sql/opt/queries/d02,d03,d05` | 三处改写：EXISTS 半连接、LATERAL 逐活动计数、先聚合后关联 |
| `scripts/gen_data.py` | 确定性生成器（seed=42，`GEN_ANCHOR` 可固定时间轴） |
| `scripts/bench.py` / `cold_bench.py` | 热/冷基准，逐条 100 次计时 + EXPLAIN 落盘 |
| `scripts/check_seed.py` | AC① 双库比对 |
| `scripts/make_report.py` | 由证据 JSON 生成 REPORT.md（数字不手抄） |
| `EVIDENCE/` | 原始 EXPLAIN（TEXT/JSON）、两轮结果 JSON、确定性核对 |

## 5. 复现

```bash
docker run -d --name cm2449-pg -e POSTGRES_DB=bench -p 55433:5432 postgres:16
python3 -m venv .venv && .venv/bin/pip install 'psycopg[binary]==3.2.3'
export DATABASE_URL=postgresql://postgres@127.0.0.1:55433/bench
.venv/bin/python scripts/init_db.py
.venv/bin/python scripts/gen_data.py --clubs 10 --seed 42
.venv/bin/python scripts/bench.py --label baseline_10clubs --runs 100 --out EVIDENCE/baseline/10clubs
.venv/bin/python scripts/cold_bench.py --label cold_baseline --out EVIDENCE/cold/baseline_10clubs
.venv/bin/python scripts/init_db.py --schema '' --indexes sql/opt/010_indexes_optimized.sql
.venv/bin/python scripts/bench.py --label optimized_10clubs --runs 100 --out EVIDENCE/optimized/10clubs --overlay sql/opt/queries
.venv/bin/python scripts/check_seed.py --clubs 10 --seed 42
.venv/bin/python scripts/make_report.py
```

## 6. 交付边界

* 单机单库、单会话只读测量；未做并发争用下的 p95（报告 §12 已列为局限，并给出压测方向）。
* 规模上限按票据 10 会所设计；再往上 d04/d05 先破线，处置顺序：物化视图 → 预聚合日表。
* 不含真实数据、不含生产连接串；`.env` 已 gitignore。
