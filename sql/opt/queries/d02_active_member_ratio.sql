-- D02 rewritten: semi-join (EXISTS) instead of DISTINCT subquery + LEFT JOIN.
-- The planner can stop at the first matching registration per enterprise
-- (index: ix_reg_ent_created) instead of materialising 20k distinct ids.
SELECT count(*) FILTER (WHERE EXISTS (
           SELECT 1 FROM registrations r
           WHERE r.enterprise_id = e.id
             AND r.club_id = %(club_id)s
             AND r.deleted_at IS NULL
             AND r.created_at >= now() - interval '90 days'
       )) AS active_enterprises,
       count(*) AS total_enterprises,
       round(100.0 * count(*) FILTER (WHERE EXISTS (
           SELECT 1 FROM registrations r
           WHERE r.enterprise_id = e.id
             AND r.club_id = %(club_id)s
             AND r.deleted_at IS NULL
             AND r.created_at >= now() - interval '90 days'
       )) / count(*), 1) AS active_pct
FROM enterprises e
WHERE e.club_id = %(club_id)s
  AND e.deleted_at IS NULL;
