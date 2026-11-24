-- Q02 Contact keyword search inside one club.
-- Screen: 联系人关键词搜索
SELECT c.id, c.name, c.title, c.phone, e.name AS enterprise_name
FROM contacts c
JOIN enterprises e ON e.id = c.enterprise_id
WHERE c.club_id = %(club_id)s
  AND c.deleted_at IS NULL
  AND (c.name ILIKE %(kw_like)s OR c.phone ILIKE %(kw_like)s OR e.name ILIKE %(kw_like)s)
ORDER BY c.created_at DESC
LIMIT 30;
