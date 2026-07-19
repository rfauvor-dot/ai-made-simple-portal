-- Run this once in the Supabase SQL editor (or via psql against the Supabase
-- connection string) before the portal's webhook creates its first user.

create table if not exists portal_users (
    id              bigint generated always as identity primary key,
    email           text not null unique,
    password_hash   text not null,
    name            text,
    is_enrolled     boolean not null default true,
    stripe_customer_id      text,
    stripe_checkout_session text,
    created_at      timestamptz not null default now()
);

create index if not exists portal_users_email_idx on portal_users (lower(email));
