-- Q04 SOP to-do list for one club: pending steps, most urgent first.
-- Screen: SOP 待办列表
SELECT s.id, s.template_id, s.step_no, s.title, s.owner_role, s.due_at
FROM sop_steps s
WHERE s.club_id = %(club_id)s
  AND s.status = 'pending'
  AND s.deleted_at IS NULL
ORDER BY s.due_at ASC
LIMIT 50;
