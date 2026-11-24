-- Q03 Registration roster of one event (name list with check-in state).
-- Screen: 活动报名名单
SELECT r.id, c.name, c.phone, e.name AS enterprise_name, r.status, r.created_at, r.checked_in_at
FROM registrations r
JOIN contacts c ON c.id = r.contact_id
JOIN enterprises e ON e.id = r.enterprise_id
WHERE r.event_id = %(event_id)s
  AND r.deleted_at IS NULL
ORDER BY r.created_at ASC;
