-- =====================================================================
-- Row Level Security Policies
-- Run AFTER 001_init_schema.sql
--
-- Role model (from profiles.role):
--   state    → sees everything, everywhere
--   district → sees everything within their org (approximated here as
--              full read access; refine org_id scoping once district
--              boundaries are modeled — flagged as a TODO below)
--   hospital → sees only batches/scans/anomalies tied to their own node
--   vendor   → sees only their own purchase_orders and related scans
--   auditor  → read-only access to everything (ledger, anomalies, batches)
-- =====================================================================

-- ---------------------------------------------------------------------
-- Enable RLS on every table
-- ---------------------------------------------------------------------
alter table drugs            enable row level security;
alter table batches          enable row level security;
alter table scan_events      enable row level security;
alter table purchase_orders  enable row level security;
alter table anomalies        enable row level security;
alter table ledger_entries   enable row level security;
alter table alerts           enable row level security;
alter table forecasts        enable row level security;
alter table profiles         enable row level security;
alter table api_keys         enable row level security;

-- ---------------------------------------------------------------------
-- Helper: current user's role (reads from profiles, avoids repeating
-- the subquery in every policy)
-- ---------------------------------------------------------------------
create or replace function auth_role() returns user_role_enum as $$
  select role from profiles where id = auth.uid();
$$ language sql stable security definer;

create or replace function auth_org_id() returns uuid as $$
  select org_id from profiles where id = auth.uid();
$$ language sql stable security definer;

-- ---------------------------------------------------------------------
-- profiles: users see their own row; state/auditor see all
-- ---------------------------------------------------------------------
create policy profiles_select on profiles for select
  using (
    id = auth.uid()
    or auth_role() in ('state', 'auditor')
  );

create policy profiles_update_self on profiles for update
  using (id = auth.uid());

-- ---------------------------------------------------------------------
-- drugs: master data, readable by everyone authenticated; writable by
-- state/district only
-- ---------------------------------------------------------------------
create policy drugs_select on drugs for select
  using (auth.role() = 'authenticated');

create policy drugs_insert on drugs for insert
  with check (auth_role() in ('state', 'district'));

create policy drugs_update on drugs for update
  using (auth_role() in ('state', 'district'));

-- ---------------------------------------------------------------------
-- batches: state/district/auditor see all; hospital/vendor see batches
-- that have a scan_event tied to their own org's node
-- ---------------------------------------------------------------------
create policy batches_select on batches for select
  using (
    auth_role() in ('state', 'district', 'auditor')
    or exists (
      select 1 from scan_events se
      join profiles p on p.id = auth.uid()
      where se.batch_id = batches.id
        and se.node_id = p.org_name -- TODO: replace with a proper node<->org mapping table
    )
  );

create policy batches_insert on batches for insert
  with check (auth_role() in ('state', 'district', 'hospital', 'vendor'));

-- ---------------------------------------------------------------------
-- scan_events: state/district/auditor see all; hospital/vendor see only
-- events at their own node
-- ---------------------------------------------------------------------
create policy scan_events_select on scan_events for select
  using (
    auth_role() in ('state', 'district', 'auditor')
    or exists (
      select 1 from profiles p
      where p.id = auth.uid() and p.org_name = scan_events.node_id
    )
  );

create policy scan_events_insert on scan_events for insert
  with check (auth.role() = 'authenticated');

-- ---------------------------------------------------------------------
-- purchase_orders: state/district/auditor see all; vendor sees only
-- their own orders
-- ---------------------------------------------------------------------
create policy po_select on purchase_orders for select
  using (
    auth_role() in ('state', 'district', 'auditor')
    or vendor_id = auth.uid()
  );

create policy po_insert on purchase_orders for insert
  with check (
    auth_role() in ('state', 'district')
    or vendor_id = auth.uid()
  );

create policy po_update on purchase_orders for update
  using (
    auth_role() in ('state', 'district')
    or vendor_id = auth.uid()
  );

-- ---------------------------------------------------------------------
-- anomalies: state/district/auditor see all; hospital sees anomalies
-- tied to batches scanned at their node
-- ---------------------------------------------------------------------
create policy anomalies_select on anomalies for select
  using (
    auth_role() in ('state', 'district', 'auditor')
    or exists (
      select 1 from scan_events se
      join profiles p on p.id = auth.uid()
      where se.batch_id = anomalies.batch_id
        and se.node_id = p.org_name
    )
  );

-- anomalies are written by the ledger service (service_role key), not
-- directly by end users — no insert policy for regular roles.
create policy anomalies_update on anomalies for update
  using (auth_role() in ('state', 'district', 'hospital'));

-- ---------------------------------------------------------------------
-- ledger_entries: read-only for everyone authenticated (transparency is
-- the point); writes happen via service_role only from the ledger service
-- ---------------------------------------------------------------------
create policy ledger_select on ledger_entries for select
  using (auth.role() = 'authenticated');

-- ---------------------------------------------------------------------
-- alerts: recipients and state/district/auditor can view
-- ---------------------------------------------------------------------
create policy alerts_select on alerts for select
  using (
    auth_role() in ('state', 'district', 'auditor')
    or recipient = (select org_name from profiles where id = auth.uid())
  );

-- ---------------------------------------------------------------------
-- forecasts: readable by everyone authenticated
-- ---------------------------------------------------------------------
create policy forecasts_select on forecasts for select
  using (auth.role() = 'authenticated');

-- ---------------------------------------------------------------------
-- api_keys: only the owner or state/admin can view; never expose key_hash
-- to the client in practice (only via the /keys creation response)
-- ---------------------------------------------------------------------
create policy api_keys_select on api_keys for select
  using (owner_id = auth.uid() or auth_role() = 'state');

create policy api_keys_insert on api_keys for insert
  with check (auth_role() = 'state');

create policy api_keys_update on api_keys for update
  using (auth_role() = 'state');
