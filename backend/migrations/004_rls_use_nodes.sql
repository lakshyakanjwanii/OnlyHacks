-- =====================================================================
-- Update RLS policies to use the nodes table instead of matching
-- scan_events.node_id against profiles.org_name as free text.
-- Run AFTER 003_nodes_mapping.sql
-- =====================================================================

-- ---------------------------------------------------------------------
-- batches: hospital/vendor see batches that have a scan_event at a
-- node belonging to their own org (via nodes.org_id = profiles.org_id)
-- ---------------------------------------------------------------------
drop policy if exists batches_select on batches;

create policy batches_select on batches for select
  using (
    auth_role() in ('state', 'district', 'auditor')
    or exists (
      select 1
      from scan_events se
      join nodes n on n.node_id = se.node_id
      where se.batch_id = batches.id
        and n.org_id = auth_org_id()
    )
  );

-- ---------------------------------------------------------------------
-- scan_events: hospital/vendor see only events at nodes belonging to
-- their own org
-- ---------------------------------------------------------------------
drop policy if exists scan_events_select on scan_events;

create policy scan_events_select on scan_events for select
  using (
    auth_role() in ('state', 'district', 'auditor')
    or exists (
      select 1 from nodes n
      where n.node_id = scan_events.node_id
        and n.org_id = auth_org_id()
    )
  );

-- ---------------------------------------------------------------------
-- anomalies: hospital sees anomalies tied to batches scanned at a node
-- belonging to their own org
-- ---------------------------------------------------------------------
drop policy if exists anomalies_select on anomalies;

create policy anomalies_select on anomalies for select
  using (
    auth_role() in ('state', 'district', 'auditor')
    or exists (
      select 1
      from scan_events se
      join nodes n on n.node_id = se.node_id
      where se.batch_id = anomalies.batch_id
        and n.org_id = auth_org_id()
    )
  );