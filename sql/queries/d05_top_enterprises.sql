-- D05 Cross-club metric: top 10 enterprises by registrations in the last 12 months.
SELECT e.id, e.name, count(r.id) AS registrations
FROM registrations r
JOIN enterprises e ON e.id = r.enterprise_id
WHERE r.deleted_at IS NULL
  AND r.created_at >= now() - interval '365 days'
GROUP BY e.id, e.name
ORDER BY registrations DESC
LIMIT 10;
