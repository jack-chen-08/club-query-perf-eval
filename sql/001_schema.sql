-- Schema for the multi-club query performance evaluation (fictional data only).
-- Every business table carries the platform-wide columns
-- id (UUID), org_id, site_id, created_at, created_by, updated_at, deleted_at.
-- Money is stored in integer cents.

DROP TABLE IF EXISTS registrations, sop_steps, opportunities, events, contacts, enterprises, clubs CASCADE;

CREATE TABLE clubs (
    id          uuid PRIMARY KEY,
    org_id      uuid        NOT NULL,
    site_id     uuid        NOT NULL,
    code        text        NOT NULL UNIQUE,
    name        text        NOT NULL,
    city        text        NOT NULL,
    opened_at   date        NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    created_by  uuid        NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now(),
    deleted_at  timestamptz
);

CREATE TABLE enterprises (
    id          uuid PRIMARY KEY,
    org_id      uuid        NOT NULL,
    site_id     uuid        NOT NULL,
    club_id     uuid        NOT NULL REFERENCES clubs (id),
    name        text        NOT NULL,
    industry    text        NOT NULL,
    scale       text        NOT NULL,
    status      text        NOT NULL,
    created_at  timestamptz NOT NULL,
    created_by  uuid        NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now(),
    deleted_at  timestamptz
);

CREATE TABLE contacts (
    id            uuid PRIMARY KEY,
    org_id        uuid        NOT NULL,
    site_id       uuid        NOT NULL,
    club_id       uuid        NOT NULL REFERENCES clubs (id),
    enterprise_id uuid        NOT NULL REFERENCES enterprises (id),
    name          text        NOT NULL,
    title         text        NOT NULL,
    phone         text        NOT NULL,
    email         text        NOT NULL,
    tags          text[]      NOT NULL DEFAULT '{}',
    created_at    timestamptz NOT NULL,
    created_by    uuid        NOT NULL,
    updated_at    timestamptz NOT NULL DEFAULT now(),
    deleted_at    timestamptz
);

CREATE TABLE events (
    id          uuid PRIMARY KEY,
    org_id      uuid        NOT NULL,
    site_id     uuid        NOT NULL,
    club_id     uuid        NOT NULL REFERENCES clubs (id),
    title       text        NOT NULL,
    category    text        NOT NULL,
    starts_at   timestamptz NOT NULL,
    seats       integer     NOT NULL,
    created_at  timestamptz NOT NULL,
    created_by  uuid        NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now(),
    deleted_at  timestamptz
);

CREATE TABLE registrations (
    id            uuid PRIMARY KEY,
    org_id        uuid        NOT NULL,
    site_id       uuid        NOT NULL,
    club_id       uuid        NOT NULL REFERENCES clubs (id),
    event_id      uuid        NOT NULL REFERENCES events (id),
    contact_id    uuid        NOT NULL REFERENCES contacts (id),
    enterprise_id uuid        NOT NULL REFERENCES enterprises (id),
    status        text        NOT NULL,
    created_at    timestamptz NOT NULL,
    checked_in_at timestamptz,
    created_by    uuid        NOT NULL,
    updated_at    timestamptz NOT NULL DEFAULT now(),
    deleted_at    timestamptz
);

CREATE TABLE sop_steps (
    id          uuid PRIMARY KEY,
    org_id      uuid        NOT NULL,
    site_id     uuid        NOT NULL,
    club_id     uuid        NOT NULL REFERENCES clubs (id),
    template_id uuid        NOT NULL,
    step_no     integer     NOT NULL,
    title       text        NOT NULL,
    owner_role  text        NOT NULL,
    status      text        NOT NULL,
    due_at      timestamptz NOT NULL,
    done_at     timestamptz,
    created_at  timestamptz NOT NULL,
    created_by  uuid        NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now(),
    deleted_at  timestamptz
);

CREATE TABLE opportunities (
    id             uuid PRIMARY KEY,
    org_id         uuid        NOT NULL,
    site_id        uuid        NOT NULL,
    club_id        uuid        NOT NULL REFERENCES clubs (id),
    enterprise_id  uuid        NOT NULL REFERENCES enterprises (id),
    stage          text        NOT NULL,
    amount_cents   bigint      NOT NULL,
    owner_id       uuid        NOT NULL,
    expected_close date        NOT NULL,
    created_at     timestamptz NOT NULL,
    created_by     uuid        NOT NULL,
    updated_at     timestamptz NOT NULL DEFAULT now(),
    deleted_at     timestamptz
);
