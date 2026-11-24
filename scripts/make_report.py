"""Build REPORT.md from the raw benchmark JSON files in EVIDENCE/."""

from __future__ import annotations

import json
import pathlib

REC = {
    "q01": ("企业列表按 会所+行业+状态 过滤、按 created_at 排序：无索引时对 3,000 行做 Filter+Sort",
            "复合部分索引 (club_id, industry, status, created_at DESC) WHERE deleted_at IS NULL"),
    "q02": ("联系人 name/phone ILIKE '%kw%'：btree 无法支持前后通配，退化为顺序扫描",
            "pg_trgm GIN 索引 (name, phone)，保留原 SQL 不动"),
    "q03": ("活动名单按 event_id 取报名：报名表 20 万行全表扫描后 Hash Join 到联系人",
            "部分索引 (event_id, created_at) WHERE deleted_at IS NULL"),
    "q04": ("SOP 待办按 会所+status 过滤、due_at 排序：50 万行扫描 + 排序",
            "部分索引 (club_id, status, due_at) WHERE deleted_at IS NULL"),
    "q05": ("商机看板按 club_id 分组 stage：全表扫描后需要回表取 amount_cents",
            "覆盖部分索引 (club_id, stage) INCLUDE (amount_cents)"),
    "d01": ("月度新增会员按 club_id + 12 个月窗口扫描企业表",
            "部分索引 (club_id, created_at) WHERE deleted_at IS NULL"),
    "d02": ("活跃会员占比用 DISTINCT 子查询 + LEFT JOIN，先物化 2 万条去重 id 再关联 300 家企业",
            "改写为 EXISTS 半连接（命中即停）+ 部分索引 (enterprise_id, created_at)"),
    "d03": ("上座率把整年报名 LEFT JOIN 回活动行再聚合，Hash Join 结果宽",
            "改写为 LATERAL 逐活动计数（每活动一次索引探针）+ (event_id) 索引"),
    "d04": ("跨会所商机漏斗需读全部 5 万行（业务上无过滤条件），只能做覆盖索引",
            "覆盖部分索引 (stage) INCLUDE (amount_cents, club_id)，走 index-only scan"),
    "d05": ("跨会所报名 TOP10 把 20 万条报名先与 3,000 家企业关联再排序",
            "改写为“先按企业聚合取 TOP10，再关联名称” + (created_at) INCLUDE (enterprise_id)"),
}


def load(p):
    f = pathlib.Path(p)
    if not f.exists():
        raise SystemExit(f"missing evidence: {p}")
    return json.loads(f.read_text(encoding="utf-8"))


def table(res: dict, cold_key: str | None = None) -> str:
    head = "| 查询 | 名称 | p50 ms | p95 ms | 目标 ms | EXPLAIN ANALYZE ms | 行数 | 结论 |"
    lines = [head, "|:--|:--|--:|--:|--:|--:|--:|:--|"]
    for qid, v in res["queries"].items():
        lines.append(f"| {qid} | {v['title']} | {v['p50_ms']} | {v['p95_ms']} | "
                     f"{v['target_ms']:.0f} | {v['snapshot_ms']} | {v['rows']} | "
                     f"{'PASS' if v['pass'] else '**FAIL**'} |")
    return "\n".join(lines)


def cold_table(res: dict) -> str:
    lines = ["| 查询 | 名称 | 冷缓存首跑 ms | 之后中位 ms | 目标 ms | 结论 |",
             "|:--|:--|--:|--:|--:|:--|"]
    for qid, v in res["queries"].items():
        lines.append(f"| {qid} | {v['title']} | {v['cold_ms']} | {v['warm_median_ms']} | "
                     f"{v['target_ms']:.0f} | {'PASS' if v['pass'] else '**FAIL**'} |")
    return "\n".join(lines)


def main() -> int:
    b1 = load("EVIDENCE/baseline/1club/results.json")
    b10 = load("EVIDENCE/baseline/10clubs/results.json")
    o10 = load("EVIDENCE/optimized/10clubs/results.json")
    cb10 = load("EVIDENCE/cold/baseline_10clubs/results_all.json")
    co10 = load("EVIDENCE/cold/optimized_10clubs/results_all.json")

    fails = [q for q, v in {**b10["queries"], **cb10["queries"]}.items()
             if not b10["queries"][q]["pass"] or not cb10["queries"][q]["pass"]]

    lines = [
        "# 多会所会员空间 · 查询性能测评报告",
        "",
        "票据 #2449 · 数据生成脚本 + 10 条查询 + EXPLAIN 记录 + 优化建议（含前后实测）",
        "",
        "## 1. 环境",
        "",
        "| 项 | 值 |",
        "|:--|:--|",
        "| 数据库 | PostgreSQL 16.16，Docker 容器 `cm2449-pg`，宿主端口 55433 |",
        "| 宿主 | WSL2 Ubuntu 24.04，1,007 GB NVMe（/dev/sdd），全部实测同机同库 |",
        "| 客户端 | Python 3.12 + psycopg 3.2.3 |",
        "| 数据 | 全虚构，名字由音节池组合，无任何真实企业/个人信息 |",
        "",
        "## 2. 数据规模",
        "",
        "| 表 | 1 会所 | 10 会所 | 单会所规则 |",
        "|:--|--:|--:|:--|",
        "| clubs | 1 | 10 | — |",
        "| enterprises | 300 | 3,000 | 每会所 300 家 |",
        "| contacts | 3,000 | 30,000 | 每企业 10 人 |",
        "| events | 600 | 6,000 | 每会所 600 场 |",
        "| registrations | 20,000 | 200,000 | 每会所 20,000 条 |",
        "| sop_steps | 50,000 | 500,000 | 1,000 模板 × 50 步 |",
        "| opportunities | 5,000 | 50,000 | 每会所 5,000 条 |",
        "",
        "1 会所全量生成 2.6 s，10 会所 21.4 s，库体积 192 MB。",
        "",
        "## 3. 种子确定性（AC①）",
        "",
        "`scripts/check_seed.py --clubs 10 --seed 42` 向两个独立库各生成一次，逐表比对行数与",
        "`sum(hashtext(id))` 校验和：七张表行数与校验和全部一致，见 `EVIDENCE/determinism.md`。",
        "唯一随日期变化的是时间戳锚点（默认取当天回溯 1080 天，可用 `GEN_ANCHOR` 固定），",
        "行数与 id 只由 seed 决定。",
        "",
        "## 4. 测试方法",
        "",
        "* 10 条查询 = 5 条列表/详情类（会所内过滤）+ 5 条驾驶舱指标（其中 2 条跨会所）。",
        "* **热缓存**：每条查询连续执行 100 次，逐次计时，报 p50/p95；另记一次",
        "  `EXPLAIN (ANALYZE, BUFFERS)` 快照。",
        "* **冷缓存**：`docker restart` 清空 shared_buffers，等待就绪后**不预热**直接计时首跑，",
        "  再取 5 次中位。冷缓存是单查询的最坏真实条件（对应“服务刚发布/被踢出缓存”）。",
        "* 目标：会所内查询 p95 < 200 ms，跨会所聚合 < 2,000 ms。",
        "",
        "## 5. 基线 · 1 会所（热缓存，100 次）",
        "",
        table(b1),
        "",
        "## 6. 基线 · 10 会所（热缓存，100 次）",
        "",
        table(b10),
        "",
        "## 7. 基线 · 10 会所（冷缓存首跑）",
        "",
        cold_table(cb10),
        "",
        "## 8. 未达标清单",
        "",
        ("**本规模下 0 条未达标**：热缓存与冷缓存首跑的最差一条分别是 d04 45 ms / 52 ms，"
         "距 2,000 ms 目标仍有一个数量级余量；会所内最差一条 q04 为 43 ms / 50 ms，"
         "距 200 ms 也有 4 倍余量。这不是“跑得快所以没问题”的结论——它说明本票据给的"
         "数据量与目标值并不构成压力，因此下表对**全部 10 条**都给了索引/改写方案，"
         "并用同一台机器实测了前后差异，而不是只补那几条“未达标”的。"
         if not fails else "未达标查询：" + "、".join(fails)),
        "",
        "## 9. 优化建议与前后实测（10 会所，热缓存 p95）",
        "",
        "| 查询 | 原方案的瓶颈 | 处理办法 | 优化前 p95 | 优化后 p95 | 提升 |",
        "|:--|:--|:--|--:|--:|--:|",
    ]
    for qid, (problem, fix) in REC.items():
        before = b10["queries"][qid]["p95_ms"]
        after = o10["queries"][qid]["p95_ms"]
        gain = before / after if after else float("inf")
        lines.append(f"| {qid} | {problem} | {fix} | {before} | {after} | **{gain:.1f}×** |")

    lines += [
        "",
        "索引全部建在 `sql/opt/010_indexes_optimized.sql`，两处改写见 `sql/opt/queries/`：",
        "",
        "* 索引一律 `WHERE deleted_at IS NULL` 的部分索引——软删除行不进任何列表与指标，",
        "  索引因此更小、更少死元组。",
        "* 复合索引遵循“等值列在前、排序列在后”：`(club_id, industry, status, created_at DESC)`。",
        "* `ILIKE '%kw%'` 无法走 btree，改 pg_trgm GIN，SQL 一字未改。",
        "* d02 的 `DISTINCT 子查询 + LEFT JOIN` 改为 `EXISTS` 半连接：每家企业在命中第一条",
        "  报名记录后即停，不再物化 2 万条去重 id。",
        "* d03 的整年 `LEFT JOIN` 改为 `LATERAL` 逐活动计数：600 次索引探针取代一次大的",
        "  Hash Join；这一条改写单独贡献了 33 ms → 1.5 ms。",
        "* d05 改为“先在报名表按企业聚合取 TOP10，再关联企业名”，避免把 20 万条报名",
        "  全部带到 JOIN 之后再排序。",
        "* d04 是唯一没有提速的（45→46 ms，噪声内）：跨会所漏斗业务上就是读全表，",
        "  只能靠覆盖索引走 index-only scan，耗时由 5 万行本身决定。这类查询不应追求",
        "  “优化到 1 ms”，它的正确处置是加缓存或物化视图，属于后续运维层，不在票据范围。",
        "",
        "## 10. 优化后 · 10 会所（热缓存 / 冷缓存）",
        "",
        table(o10),
        "",
        cold_table(co10),
        "",
        "## 11. 冷热差说明了什么",
        "",
        "基线冷热差最大的是 q04（50 ms → 43 ms）与 q03（28 ms → 20 ms），即顺序扫描型查询",
        "对缓存敏感；优化后这两条的冷热差压到 3 ms / 6 ms，因为索引访问的页数本来就少。",
        "这也是索引在本规模下的真正价值：不是把 43 ms 变成 0.8 ms 好看，而是把“缓存一旦变冷",
        "就退化成全表扫描”的风险去掉。",
        "",
        "## 12. 局限与未做的部分",
        "",
        "* 单机单库、无并发。10 条查询都是只读单条测量，未做多会话争用下的 p95；",
        "  若按 10 会所 × 每会所 20 名员工同时在线估，连接池与并发上限需要另行压测。",
        "* 规模只到 10 会所（20 万报名）。再往上（如 100 会所）d04/d05 会先破线，",
        "  处置顺序是：物化视图 → 预聚合日表，而不是继续加索引。",
        "* 未做查询计划回归测试；建议把 `EVIDENCE/*/q*.explain.txt` 纳入 CI 做计划漂移比对。",
        "",
        "## 13. 复现",
        "",
        "```bash",
        "docker run -d --name cm2449-pg -e POSTGRES_DB=bench -p 55433:5432 postgres:16",
        "python3 -m venv .venv && .venv/bin/pip install 'psycopg[binary]==3.2.3'",
        "export DATABASE_URL=postgresql://postgres@127.0.0.1:55433/bench",
        ".venv/bin/python scripts/init_db.py                    # 建表 + 基线索引",
        ".venv/bin/python scripts/gen_data.py --clubs 10 --seed 42",
        ".venv/bin/python scripts/bench.py --label baseline_10clubs --runs 100 --out EVIDENCE/baseline/10clubs",
        ".venv/bin/python scripts/cold_bench.py --label cold_baseline --out EVIDENCE/cold/baseline_10clubs",
        ".venv/bin/python scripts/init_db.py --schema '' --indexes sql/opt/010_indexes_optimized.sql",
        ".venv/bin/python scripts/bench.py --label optimized_10clubs --runs 100 --out EVIDENCE/optimized/10clubs --overlay sql/opt/queries",
        ".venv/bin/python scripts/check_seed.py --clubs 10 --seed 42",
        "```",
        "",
    ]
    pathlib.Path("REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("REPORT.md written,", len(lines), "lines; fails =", fails or "none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
