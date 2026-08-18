-- =====================================================================
-- Track A — Anon read bypass (demo safety net)
-- Run AFTER 002_rls_policies.sql
--
-- WHY: The dashboard (and all API consumers without a Supabase session)
-- hit the backend as the `anon` role. RLS policies in 002 only grant
-- SELECT to `authenticated` (logged-in) users, so every GET returns [].
-- These policies extend SELECT to `anon` on read-only, non-sensitive
-- tables — drugs, batches, scan_events, anomalies, alerts — so the
-- dashboard shows real seeded data without requiring a login first.
--
-- SECURITY NOTE: This is intentionally permissive for READ only.
-- All INSERT / UPDATE operations remain gated by JWT (see 002).
-- ledger_entries, api_keys, profiles remain auth-only even for reads.
-- In a production deployment you would remove or tighten these policies
-- once the login flow (Track B) is confirmed working.
-- =====================================================================

-- drugs: public master data — safe to expose to anyone
create policy drugs_anon_select on drugs for select
  to anon
  using (true);

-- batches: supply chain lineage — readable without login for dashboard
create policy batches_anon_select on batches for select
  to anon
  using (true);

-- scan_events: logistics map data — readable without login
create policy scan_events_anon_select on scan_events for select
  to anon
  using (true);

-- anomalies: dashboard feed — readable without login
create policy anomalies_anon_select on anomalies for select
  to anon
  using (true);

-- alerts: dashboard feed — readable without login
create policy alerts_anon_select on alerts for select
  to anon
  using (true);

-- forecasts: ML output, safe to show publicly
create policy forecasts_anon_select on forecasts for select
  to anon
  using (true);
