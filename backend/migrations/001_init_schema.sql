-- =====================================================================
-- Drug Supply Chain Control Tower — Initial Schema
-- PSS04 · Smart India Hackathon
-- Run this in Supabase SQL Editor, or via `supabase db push`
-- =====================================================================

create extension if not exists "uuid-ossp";
create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------
-- ENUM TYPES
-- ---------------------------------------------------------------------
create type node_type_enum as enum ('factory', 'warehouse', 'hospital', 'vendor');
create type po_status_enum as enum ('pending', 'shipped', 'delivered');
create type user_role_enum as enum ('state', 'district', 'hospital', 'vendor', 'auditor');

-- ---------------------------------------------------------------------
-- profiles — extends auth.users with role + org context
-- ---------------------------------------------------------------------
create table profiles (
    id          uuid primary key references auth.users(id) on delete cascade,
    role        user_role_enum not null,
    org_name    text not null,
    org_id      uuid default uuid_generate_v4(), -- groups users under the same org for RLS
    created_at  timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- drugs
-- ---------------------------------------------------------------------
create table drugs (
    id           uuid primary key default uuid_generate_v4(),
    name         text not null,
    manufacturer text not null,
    gtin         text not null unique,           -- GS1 Global Trade Item Number
    created_at   timestamptz not null default now()
);

create index idx_drugs_gtin on drugs(gtin);

-- ---------------------------------------------------------------------
-- batches
-- ---------------------------------------------------------------------
create table batches (
    id               uuid primary key default uuid_generate_v4(),
    drug_id          uuid not null references drugs(id) on delete cascade,
    batch_number     text not null,
    manufacture_date date not null,
    expiry_date      date not null,
    created_at       timestamptz not null default now()
);

-- NOTE: deliberately NOT unique on (drug_id, batch_number) — the CAG bug
-- this system exists to catch is exactly two rows with the same
-- drug+batch_number but different expiry_date. Uniqueness is enforced
-- logically by the anomaly engine (teammate 3), not by a DB constraint.
create index idx_batches_drug_id on batches(drug_id);
create index idx_batches_batch_number on batches(batch_number);
create index idx_batches_expiry on batches(expiry_date);

-- ---------------------------------------------------------------------
-- scan_events
-- ---------------------------------------------------------------------
create table scan_events (
    id           uuid primary key default uuid_generate_v4(),
    batch_id     uuid not null references batches(id) on delete cascade,
    node_type    node_type_enum not null,
    node_id      text not null,          -- e.g. warehouse code, hospital ID
    scanned_by   uuid references profiles(id),
    location     text,
    timestamp    timestamptz not null default now(),
    raw_payload  jsonb,                  -- raw GS1 string / decoded fields from scanner
    created_at   timestamptz not null default now()
);

create index idx_scan_events_batch_id on scan_events(batch_id);
create index idx_scan_events_node on scan_events(node_type, node_id);

-- ---------------------------------------------------------------------
-- purchase_orders
-- ---------------------------------------------------------------------
create table purchase_orders (
    id         uuid primary key default uuid_generate_v4(),
    vendor_id  uuid not null references profiles(id),
    drug_id    uuid not null references drugs(id),
    quantity   integer not null check (quantity > 0),
    status     po_status_enum not null default 'pending',
    created_at timestamptz not null default now()
);

create index idx_po_vendor on purchase_orders(vendor_id);
create index idx_po_drug on purchase_orders(drug_id);

-- ---------------------------------------------------------------------
-- anomalies — written by teammate 3's rule engine
-- ---------------------------------------------------------------------
create table anomalies (
    id             uuid primary key default uuid_generate_v4(),
    batch_id       uuid references batches(id) on delete cascade,
    rule_triggered text not null,     -- e.g. 'batch_expiry_consistency'
    details        jsonb,
    resolved       boolean not null default false,
    created_at     timestamptz not null default now()
);

create index idx_anomalies_batch on anomalies(batch_id);
create index idx_anomalies_resolved on anomalies(resolved);

-- ---------------------------------------------------------------------
-- ledger_entries — hash-chain, written by teammate 3
-- ---------------------------------------------------------------------
create table ledger_entries (
    id         uuid primary key default uuid_generate_v4(),
    ref_table  text not null,         -- which table this entry is about
    ref_id     uuid not null,         -- row id in that table
    data_hash  text not null,
    prev_hash  text,                  -- null only for the very first entry
    created_at timestamptz not null default now()
);

create index idx_ledger_ref on ledger_entries(ref_table, ref_id);
create index idx_ledger_created on ledger_entries(created_at);

-- ---------------------------------------------------------------------
-- alerts — written by teammate 5's notification service
-- ---------------------------------------------------------------------
create table alerts (
    id         uuid primary key default uuid_generate_v4(),
    type       text not null,         -- 'stockout_risk' | 'anomaly' | 'expiry_risk'
    message    text not null,
    recipient  text not null,
    sent_at    timestamptz,
    channel    text not null,         -- 'whatsapp' | 'sms' | 'dashboard'
    created_at timestamptz not null default now()
);

create index idx_alerts_type on alerts(type);

-- ---------------------------------------------------------------------
-- forecasts — written by teammate 5's ML service, read by frontend
-- ---------------------------------------------------------------------
create table forecasts (
    id                    uuid primary key default uuid_generate_v4(),
    drug_id               uuid not null references drugs(id) on delete cascade,
    date                  date not null,
    predicted_stock       numeric,
    predicted_stockout_date date,
    reorder_threshold     numeric,
    created_at            timestamptz not null default now()
);

create index idx_forecasts_drug on forecasts(drug_id);

-- ---------------------------------------------------------------------
-- api_keys — for external/vendor system integrations
-- ---------------------------------------------------------------------
create table api_keys (
    id         uuid primary key default uuid_generate_v4(),
    key_hash   text not null unique,   -- sha256 hash of the raw key; raw key never stored
    owner_id   uuid references profiles(id),
    scopes     text[] not null default '{}',  -- e.g. {'scan_events:write','purchase_orders:read'}
    created_at timestamptz not null default now(),
    revoked    boolean not null default false
);

create index idx_api_keys_hash on api_keys(key_hash);
