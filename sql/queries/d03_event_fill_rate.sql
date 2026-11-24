-- D03 Dashboard metric 3: average event fill rate (registrations / seats) per club,
-- events in the last 12 months, one club.
SELECT round(avg(fill.rate), 3) AS avg_fill_rate, count(*) AS events_counted
FROM (
    SELECT e.id, LEAST(1.0, count(r.id)::numeric / NULLIF(e.seats, 0)) AS rate
    FROM events e
    LEFT JOIN registrations r ON r.event_id = e.id AND r.deleted_at IS NULL
    WHERE e.club_id = %(club_id)s
      AND e.deleted_at IS NULL
      AND e.starts_at >= now() - interval '365 days'
    GROUP BY e.id, e.seats
) fill;
