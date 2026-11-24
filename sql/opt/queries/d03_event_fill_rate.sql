-- D03 rewritten: per-event LATERAL count. With ix_reg_event_created the inner
-- count is a cheap index-only probe per event, so only the club's events are
-- touched; the original hash-joined a year of registrations for every club.
SELECT round(avg(LEAST(1.0, COALESCE(x.cnt, 0)::numeric / NULLIF(e.seats, 0))), 3) AS avg_fill_rate,
       count(*) AS events_counted
FROM events e
LEFT JOIN LATERAL (
    SELECT count(*) AS cnt
    FROM registrations r
    WHERE r.event_id = e.id
      AND r.deleted_at IS NULL
) x ON true
WHERE e.club_id = %(club_id)s
  AND e.deleted_at IS NULL
  AND e.starts_at >= now() - interval '365 days';
