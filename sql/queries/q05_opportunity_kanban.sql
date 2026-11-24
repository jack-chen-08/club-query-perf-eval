-- Q05 Opportunity kanban: per-stage count and value for one club.
-- Screen: 商机看板分组计数
SELECT o.stage,
       count(*)               AS opportunities,
       sum(o.amount_cents)    AS amount_cents
FROM opportunities o
WHERE o.club_id = %(club_id)s
  AND o.deleted_at IS NULL
GROUP BY o.stage
ORDER BY o.stage;
