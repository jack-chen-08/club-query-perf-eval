-- D02 Dashboard metric 2: active-member ratio — enterprises with at least one
-- event registration in the last 90 days, over all enterprises of one club.
SELECT count(*) FILTER (WHERE active.enterprise_id IS NOT NULL) AS active_enterprises,
       count(*)                                               AS total_enterprises,
       round(100.0 * count(*) FILTER (WHERE active.enterprise_id IS NOT NULL) / count(*), 1) AS active_pct
FROM enterprises e
LEFT JOIN (
    SELECT DISTINCT r.enterprise_id
    FROM registrations r
    WHERE r.club_id = %(club_id)s
      AND r.deleted_at IS NULL
      AND r.created_at >= now() - interval '90 days'
) active ON active.enterprise_id = e.id
WHERE e.club_id = %(club_id)s
  AND e.deleted_at IS NULL;
