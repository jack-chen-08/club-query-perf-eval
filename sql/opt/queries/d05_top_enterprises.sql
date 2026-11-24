-- D05 rewritten: aggregate registrations first, join enterprise names only for
-- the ten surviving rows. The original joined 200k registrations to enterprises
-- before sorting, which forced a hash join over the whole year of data.
SELECT e.id, e.name, t.registrations
FROM (
    SELECT r.enterprise_id, count(*) AS registrations
    FROM registrations r
    WHERE r.deleted_at IS NULL
      AND r.created_at >= now() - interval '365 days'
    GROUP BY r.enterprise_id
    ORDER BY registrations DESC
    LIMIT 10
) t
JOIN enterprises e ON e.id = t.enterprise_id
ORDER BY t.registrations DESC;
