-- Baseline: primary keys and the natural keys declared by the CRM / SOP tickets.
-- No secondary indexes are created here on purpose: this is what the upstream
-- tickets ship, and it is the starting point the evaluation measures.
-- (PostgreSQL does not index foreign keys automatically.)

CREATE UNIQUE INDEX ux_clubs_code ON clubs (code);
