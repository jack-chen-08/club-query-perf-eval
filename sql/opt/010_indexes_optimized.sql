-- Optimization layer for the ten evaluation queries.
-- Every index is partial on `deleted_at IS NULL` because soft-deleted rows are
-- never part of a list, roster or metric. Composite key order follows the
-- equality-then-range rule: filter columns first, sort column last.

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Q01 enterprise list: equality on club/industry/status, range+sort on created_at
CREATE INDEX IF NOT EXISTS ix_ent_club_industry_status
    ON enterprises (club_id, industry, status, created_at DESC)
    WHERE deleted_at IS NULL;

-- D01 monthly new enterprises: club + created_at window
CREATE INDEX IF NOT EXISTS ix_ent_club_created
    ON enterprises (club_id, created_at)
    WHERE deleted_at IS NULL;

-- Q02 keyword search: ILIKE '%kw%' cannot use a btree, use trigram GIN
CREATE INDEX IF NOT EXISTS ix_ctc_name_trgm
    ON contacts USING gin (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS ix_ctc_phone_trgm
    ON contacts USING gin (phone gin_trgm_ops);
CREATE INDEX IF NOT EXISTS ix_ctc_club_created
    ON contacts (club_id, created_at DESC)
    WHERE deleted_at IS NULL;

-- Q03 roster and D03 fill rate: registrations per event
CREATE INDEX IF NOT EXISTS ix_reg_event_created
    ON registrations (event_id, created_at)
    WHERE deleted_at IS NULL;

-- D02 active member ratio / D05 top enterprises / D04 funnel: per club + window
CREATE INDEX IF NOT EXISTS ix_reg_club_created
    ON registrations (club_id, created_at)
    WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS ix_reg_created_ent
    ON registrations (created_at) INCLUDE (enterprise_id)
    WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS ix_reg_ent_created
    ON registrations (enterprise_id, created_at)
    WHERE deleted_at IS NULL;

-- Q04 SOP to-do: equality on club+status, sort on due_at
CREATE INDEX IF NOT EXISTS ix_sop_todo
    ON sop_steps (club_id, status, due_at)
    WHERE deleted_at IS NULL;

-- Q05 kanban: club + stage grouping, amount covered by the index
CREATE INDEX IF NOT EXISTS ix_opp_club_stage
    ON opportunities (club_id, stage) INCLUDE (amount_cents)
    WHERE deleted_at IS NULL;

-- D04 cross-club funnel: stage grouping over all clubs, index-only scan
CREATE INDEX IF NOT EXISTS ix_opp_stage
    ON opportunities (stage) INCLUDE (amount_cents, club_id)
    WHERE deleted_at IS NULL;

-- D03 fill rate: events of a club inside a time window
CREATE INDEX IF NOT EXISTS ix_evt_club_starts
    ON events (club_id, starts_at)
    WHERE deleted_at IS NULL;

ANALYZE;
