-- D01 Dashboard metric 1: new member enterprises per month, last 12 months, one club.
SELECT date_trunc('month', e.created_at) AS month, count(*) AS new_enterprises
FROM enterprises e
WHERE e.club_id = %(club_id)s
  AND e.deleted_at IS NULL
  AND e.created_at >= now() - interval '365 days'
GROUP BY 1
ORDER BY 1;
