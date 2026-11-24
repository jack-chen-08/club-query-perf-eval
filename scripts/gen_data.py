"""Deterministic fictional data generator for the multi-club performance evaluation.

Every row is derived from a fixed seed, so two runs produce identical ids, values,
row counts and checksums. All names are synthetic; no real company, person or
contact data is used.

Target volume per club:
    300 enterprises, 3,000 contacts, 600 events, 20,000 registrations,
    50,000 SOP step records, 5,000 opportunities

Usage:
    export DATABASE_URL=postgresql://postgres:***@127.0.0.1:55433/bench
    python scripts/gen_data.py --clubs 10 --seed 42
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone

import psycopg

ORG_ID = uuid.uuid5(uuid.NAMESPACE_DNS, "member-space.example")
ADMIN_ID = uuid.uuid5(uuid.NAMESPACE_DNS, "user:admin")
NS = uuid.UUID("6f9619ff-8b86-d011-b42d-00c04fc964ff")

SYL_A = ["星", "澜", "恒", "瑞", "嘉", "远", "锦", "衡", "知", "云", "合", "朗", "泓", "泰", "朴", "澄"]
SYL_B = ["海", "岸", "川", "谷", "林", "原", "舟", "图", "序", "野", "桥", "筑", "仓", "塔", "庭", "径"]
SYL_C = ["科技", "实业", "咨询", "智能", "供应链", "文化", "设计", "贸易", "数据", "物流", "医疗", "能源"]
INDUSTRIES = ["manufacturing", "retail", "logistics", "finance", "healthcare",
              "education", "technology", "real_estate", "hospitality", "energy"]
SCALES = ["micro", "small", "medium", "large"]
ENT_STATUS = ["prospect", "member", "renewing", "churned"]
TITLES = ["总经理", "招商总监", "运营经理", "采购主管", "技术负责人", "行政经理", "合伙人"]
TAGS = ["高潜", "重点招商", "已缴费", "待跟进", "政府关系", "供应链", "跨境"]
EVENT_CATS = ["industry_salon", "training", "policy_briefing", "matchmaking", "annual_gala"]
EVENT_WORDS = ["沙龙", "训练营", "政策解读", "对接会", "年会"]
SOP_ROLES = ["招商专员", "会务", "客户成功", "财务", "运营"]
SOP_STATUS = ["pending", "doing", "done", "skipped"]
SOP_WORDS = ["签约跟进", "资料归档", "费用核对", "回访", "排期"]
OPP_STAGES = ["lead", "qualified", "proposal", "negotiation", "won", "lost"]
REG_STATUS = ["registered", "checked_in", "cancelled", "no_show"]

PER_CLUB = dict(enterprises=300, contacts_per_enterprise=10, events=600,
                registrations=20000, sop_templates=1000, sop_steps_per_template=50,
                opportunities=5000)


def uid(kind: str, seq: int) -> uuid.UUID:
    return uuid.uuid5(NS, f"{kind}:{seq}")


def unique_names(rng: random.Random, n: int, used: set[str]) -> list[str]:
    out: list[str] = []
    guard = 0
    while len(out) < n and guard < n * 60:
        guard += 1
        nm = rng.choice(SYL_A) + rng.choice(SYL_B) + rng.choice(SYL_C)
        if nm not in used:
            used.add(nm)
            out.append(nm)
    while len(out) < n:
        out.append("虚构企业" + str(len(out) + 1))
    return out


def copy_rows(cur, table: str, columns: list[str], rows: list[tuple]) -> int:
    with cur.copy(f"COPY {table} ({', '.join(columns)}) FROM STDIN") as cp:
        for row in rows:
            cp.write_row(row)
    return len(rows)


ENT_COLS = ["id", "org_id", "site_id", "club_id", "name", "industry", "scale", "status",
            "created_at", "created_by", "updated_at"]
CTC_COLS = ["id", "org_id", "site_id", "club_id", "enterprise_id", "name", "title", "phone",
            "email", "tags", "created_at", "created_by", "updated_at"]
EVT_COLS = ["id", "org_id", "site_id", "club_id", "title", "category", "starts_at", "seats",
            "created_at", "created_by", "updated_at"]
REG_COLS = ["id", "org_id", "site_id", "club_id", "event_id", "contact_id", "enterprise_id",
            "status", "created_at", "checked_in_at", "created_by", "updated_at"]
SOP_COLS = ["id", "org_id", "site_id", "club_id", "template_id", "step_no", "title", "owner_role",
            "status", "due_at", "done_at", "created_at", "created_by", "updated_at"]
OPP_COLS = ["id", "org_id", "site_id", "club_id", "enterprise_id", "stage", "amount_cents",
            "owner_id", "expected_close", "created_at", "created_by", "updated_at"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clubs", type=int, default=10)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--dsn", default=os.environ.get("DATABASE_URL"))
    ap.add_argument("--keep", action="store_true", help="do not truncate existing rows")
    args = ap.parse_args()
    if not args.dsn:
        print("DATABASE_URL is not set", file=sys.stderr)
        return 2

    rng = random.Random(args.seed)
    # Anchor the timeline 3 years back from a fixed anchor so that the
    # "last 12 months" dashboard windows contain data. Row counts depend only
    # on --seed, never on the anchor date.
    anchor_raw = os.environ.get("GEN_ANCHOR")
    anchor = (datetime.fromisoformat(anchor_raw) if anchor_raw
              else datetime.now(timezone.utc)).replace(hour=0, minute=0, second=0, microsecond=0)
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=timezone.utc)
    base = anchor - timedelta(days=1080)
    totals = dict(clubs=0, enterprises=0, contacts=0, events=0, registrations=0,
                  sop_steps=0, opportunities=0)
    used_names: set[str] = set()

    with psycopg.connect(args.dsn) as conn, conn.cursor() as cur:
        if not args.keep:
            cur.execute("TRUNCATE registrations, sop_steps, opportunities, events, "
                        "contacts, enterprises, clubs CASCADE")

        club_ids = [uid("club", c) for c in range(args.clubs)]
        rows = []
        for c, cid in enumerate(club_ids):
            rows.append((cid, ORG_ID, cid, f"C{c + 1:03d}",
                         rng.choice(SYL_A) + rng.choice(SYL_B) + "会所",
                         rng.choice(["上海", "深圳", "杭州", "成都", "苏州", "武汉"]),
                         base.date() - timedelta(days=rng.randint(200, 1500)),
                         base, ADMIN_ID, base))
        totals["clubs"] = copy_rows(cur, "clubs", ["id", "org_id", "site_id", "code", "name", "city",
                                                   "opened_at", "created_at", "created_by", "updated_at"], rows)

        for c, cid in enumerate(club_ids):
            # ---- enterprises ----
            ents, ctc_ids = [], []
            for nm in unique_names(rng, PER_CLUB["enterprises"], used_names):
                eid = uid("ent", c * 10000 + len(ents))
                created = base + timedelta(days=rng.randint(0, 1000), seconds=rng.randint(0, 86399))
                ents.append((eid, ORG_ID, cid, cid, nm, rng.choice(INDUSTRIES), rng.choice(SCALES),
                             rng.choice(ENT_STATUS), created, ADMIN_ID, created))
            totals["enterprises"] += copy_rows(cur, "enterprises", ENT_COLS, ents)
            ent_ids = [e[0] for e in ents]

            # ---- contacts (10 per enterprise) ----
            ctc_rows = []
            for i, eid in enumerate(ent_ids):
                created = base + timedelta(days=rng.randint(0, 1000), seconds=rng.randint(0, 86399))
                for k in range(PER_CLUB["contacts_per_enterprise"]):
                    ctc = uid("ctc", c * 100000 + i * 10 + k)
                    ctc_ids.append(ctc)
                    ctc_rows.append((ctc, ORG_ID, cid, cid, eid,
                                     rng.choice(SYL_A) + rng.choice(SYL_B), rng.choice(TITLES),
                                     f"13{rng.randint(100000000, 999999999)}",
                                     f"u{c * 100000 + i * 10 + k}@example.invalid",
                                     [rng.choice(TAGS)], created, ADMIN_ID, created))
            totals["contacts"] += copy_rows(cur, "contacts", CTC_COLS, ctc_rows)

            # ---- events ----
            evt_rows = []
            for i in range(PER_CLUB["events"]):
                ev = uid("ev", c * 10000 + i)
                starts = base + timedelta(days=rng.randint(0, 1000), hours=rng.randint(9, 20))
                evt_rows.append((ev, ORG_ID, cid, cid,
                                 rng.choice(SYL_A) + rng.choice(SYL_B) + rng.choice(EVENT_WORDS),
                                 rng.choice(EVENT_CATS), starts, rng.choice([30, 60, 100, 200]),
                                 starts - timedelta(days=30), ADMIN_ID, starts - timedelta(days=30)))
            totals["events"] += copy_rows(cur, "events", EVT_COLS, evt_rows)
            ev_ids = [e[0] for e in evt_rows]

            # ---- registrations (exactly 20,000 per club) ----
            reg_rows = []
            for n in range(PER_CLUB["registrations"]):
                created = base + timedelta(days=rng.randint(0, 1000), seconds=rng.randint(0, 86399))
                idx = rng.randrange(len(ent_ids))
                reg_rows.append((uid("reg", c * 100000 + n), ORG_ID, cid, cid,
                                 ev_ids[rng.randrange(len(ev_ids))], ctc_ids[idx * 10],
                                 ent_ids[idx], rng.choice(REG_STATUS), created, None, ADMIN_ID, created))
            totals["registrations"] += copy_rows(cur, "registrations", REG_COLS, reg_rows)

            # ---- sop steps (1,000 templates x 50 steps) ----
            sop_rows = []
            n = 0
            for t in range(PER_CLUB["sop_templates"]):
                tpl = uid("tpl", c * 10000 + t)
                for s in range(PER_CLUB["sop_steps_per_template"]):
                    created = base + timedelta(days=rng.randint(0, 1000), seconds=rng.randint(0, 86399))
                    due = created + timedelta(days=rng.randint(0, 30))
                    st = rng.choice(SOP_STATUS)
                    sop_rows.append((uid("sop", c * 100000 + n), ORG_ID, cid, cid, tpl, s + 1,
                                     f"步骤{s + 1}·{rng.choice(SOP_WORDS)}", rng.choice(SOP_ROLES),
                                     st, due, due if st == "done" else None, created, ADMIN_ID, created))
                    n += 1
            totals["sop_steps"] += copy_rows(cur, "sop_steps", SOP_COLS, sop_rows)

            # ---- opportunities ----
            opp_rows = []
            for i in range(PER_CLUB["opportunities"]):
                created = base + timedelta(days=rng.randint(0, 1000), seconds=rng.randint(0, 86399))
                opp_rows.append((uid("opp", c * 100000 + i), ORG_ID, cid, cid,
                                 ent_ids[rng.randrange(len(ent_ids))], rng.choice(OPP_STAGES),
                                 rng.randint(100, 2000) * 100, uid("user", rng.randint(1, 40)),
                                 (created + timedelta(days=rng.randint(10, 180))).date(),
                                 created, ADMIN_ID, created))
            totals["opportunities"] += copy_rows(cur, "opportunities", OPP_COLS, opp_rows)
            conn.commit()

        cur.execute("ANALYZE")
        conn.commit()

    print(f"seed={args.seed} clubs={args.clubs}")
    for k in ["clubs", "enterprises", "contacts", "events", "registrations", "sop_steps", "opportunities"]:
        print(f"{k}={totals[k]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
