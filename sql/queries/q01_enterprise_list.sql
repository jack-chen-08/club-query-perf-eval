-- Q01 Enterprise list, filtered by club + industry + status, newest first.
-- Screen: 会员企业列表筛选
SELECT e.id, e.name, e.industry, e.scale, e.status, e.created_at
FROM enterprises e
WHERE e.club_id = %(club_id)s
  AND e.deleted_at IS NULL
  AND e.industry = %(industry)s
  AND e.status = %(status)s
ORDER BY e.created_at DESC
LIMIT 20 OFFSET 0;
