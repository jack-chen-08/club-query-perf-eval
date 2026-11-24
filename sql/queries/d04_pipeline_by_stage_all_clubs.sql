-- D04 Cross-club metric: pipeline value and count per stage across all clubs
-- (the "驾驶舱" summary row — no club filter, so it must scan every club).
SELECT o.stage,
       count(*)            AS opportunities,
       sum(o.amount_cents) AS amount_cents,
       count(DISTINCT o.club_id) AS clubs
FROM opportunities o
WHERE o.deleted_at IS NULL
GROUP BY o.stage
ORDER BY amount_cents DESC;
