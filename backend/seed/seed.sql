-- =====================================================================
-- Seed data v2 — realistic mock data + deliberate CAG-pattern conflict
-- + seeded alerts + seeded forecasts for immediate dashboard data
--
-- Run AFTER 001_init_schema.sql, 002_rls_policies.sql, and
-- 005_anon_read_bypass.sql.
-- Must be run as service_role (Supabase SQL Editor or SUPABASE_SERVICE_KEY)
-- since RLS blocks unauthenticated inserts on most tables.
-- =====================================================================

-- =====================================================================
-- SECTION 1: DRUGS
-- =====================================================================
insert into drugs (id, name, manufacturer, gtin) values
  ('11111111-1111-1111-1111-111111111111', 'Paracetamol 500mg',   'Cipla Ltd',           '08901234567892'),
  ('22222222-2222-2222-2222-222222222222', 'Amoxicillin 250mg',   'Sun Pharma',           '08901234567908'),
  ('33333333-3333-3333-3333-333333333333', 'ORS Sachets',         'Zydus Lifesciences',   '08901234567915'),
  ('44444444-4444-4444-4444-444444444444', 'Insulin Glargine',    'Biocon',               '08901234567922'),
  ('55555555-5555-5555-5555-555555555555', 'Azithromycin 500mg',  'Cipla Ltd',            '08901234567939')
on conflict (id) do nothing;

-- =====================================================================
-- SECTION 2: BATCHES — normal clean records
-- =====================================================================
insert into batches (id, drug_id, batch_number, manufacture_date, expiry_date) values
  ('aaaaaaaa-0001-0001-0001-000000000001', '11111111-1111-1111-1111-111111111111', 'PCM-2025-A01', '2025-01-10', '2027-01-10'),
  ('aaaaaaaa-0001-0001-0001-000000000002', '22222222-2222-2222-2222-222222222222', 'AMX-2025-B02', '2025-02-15', '2027-02-15'),
  ('aaaaaaaa-0001-0001-0001-000000000003', '33333333-3333-3333-3333-333333333333', 'ORS-2025-C03', '2025-03-01', '2026-09-01'),
  ('aaaaaaaa-0001-0001-0001-000000000004', '44444444-4444-4444-4444-444444444444', 'INS-2025-D04', '2025-04-20', '2026-10-20'),
  ('aaaaaaaa-0001-0001-0001-000000000005', '55555555-5555-5555-5555-555555555555', 'AZI-2025-E05', '2025-05-05', '2027-05-05')
on conflict (id) do nothing;

-- =====================================================================
-- ⚠  THE CAG-PATTERN CONFLICT — demo centerpiece ⚠
--
-- Same drug_id + same batch_number ('PCM-2025-A01') as row ...001 above,
-- but a DIFFERENT expiry_date (2027-06-15 vs 2027-01-10).
-- This is EXACTLY the bug the CAG found 636 times in e-Aushadhi.
-- Teammate 3's anomaly engine should detect this the moment it scans
-- the batches table (or immediately after this row is written).
-- =====================================================================
insert into batches (id, drug_id, batch_number, manufacture_date, expiry_date) values
  ('aaaaaaaa-0001-0001-0001-000000000099',
   '11111111-1111-1111-1111-111111111111',  -- same drug (Paracetamol / Cipla)
   'PCM-2025-A01',                           -- same batch_number
   '2025-01-10',
   '2027-06-15')                             -- ← DIFFERENT expiry — the conflict
on conflict (id) do nothing;
-- Row ...001: expiry 2027-01-10  |  Row ...099: expiry 2027-06-15
-- Anomaly rule to trigger: 'batch_expiry_consistency'

-- =====================================================================
-- SECTION 3: SCAN EVENTS
-- factory → warehouse → hospital journey for batch PCM-2025-A01
-- =====================================================================
insert into scan_events (batch_id, node_type, node_id, location, raw_payload) values
  ('aaaaaaaa-0001-0001-0001-000000000001', 'factory',   'CIPLA-FACTORY-MUM',          'Mumbai, MH',  '{"gtin":"08901234567892","batch":"PCM-2025-A01","step":"dispatch"}'),
  ('aaaaaaaa-0001-0001-0001-000000000001', 'warehouse',  'MH-STATE-WAREHOUSE-01',      'Pune, MH',    '{"gtin":"08901234567892","batch":"PCM-2025-A01","step":"receipt"}'),
  ('aaaaaaaa-0001-0001-0001-000000000001', 'hospital',   'DISTRICT-HOSPITAL-NASHIK',   'Nashik, MH',  '{"gtin":"08901234567892","batch":"PCM-2025-A01","step":"handoff"}'),
  -- AMX batch is currently in transit at a vendor hub
  ('aaaaaaaa-0001-0001-0001-000000000002', 'vendor',     'SUNPHARMA-DIST-PUNE',        'Pune, MH',    '{"gtin":"08901234567908","batch":"AMX-2025-B02","step":"shipped"}'),
  -- INS batch scanned at hospital (expiring soon — good for FEFO alert)
  ('aaaaaaaa-0001-0001-0001-000000000004', 'hospital',   'AIIMS-DELHI-PHARMACY',       'New Delhi',   '{"gtin":"08901234567922","batch":"INS-2025-D04","step":"receipt"}')
on conflict do nothing;

-- =====================================================================
-- SECTION 4: ANOMALIES — pre-seeded so dashboard is non-empty
-- (teammate 3's engine will add more once it processes the conflict batch)
-- =====================================================================
insert into anomalies (id, batch_id, rule_triggered, details, resolved) values
  (
    'cccccccc-0001-0001-0001-000000000001',
    'aaaaaaaa-0001-0001-0001-000000000001',  -- PCM-2025-A01
    'batch_expiry_consistency',
    '{"conflict": "Two rows for PCM-2025-A01 (drug: Paracetamol 500mg, mfr: Cipla Ltd) have differing expiry_date values: 2027-01-10 vs 2027-06-15. Matches CAG e-Aushadhi pattern (636 incidents).", "batch_ids": ["aaaaaaaa-0001-0001-0001-000000000001","aaaaaaaa-0001-0001-0001-000000000099"], "severity": "HIGH"}',
    false
  ),
  (
    'cccccccc-0001-0001-0001-000000000002',
    'aaaaaaaa-0001-0001-0001-000000000004',  -- INS-2025-D04 (expires Oct 2026)
    'expiry_within_60_days',
    '{"message": "Insulin Glargine batch INS-2025-D04 expires 2026-10-20 — within 60-day FEFO alert window.", "days_remaining": 63, "severity": "MEDIUM"}',
    false
  ),
  (
    'cccccccc-0001-0001-0001-000000000003',
    'aaaaaaaa-0001-0001-0001-000000000003',  -- ORS-2025-C03 (expires Sep 2026)
    'expiry_within_60_days',
    '{"message": "ORS Sachets batch ORS-2025-C03 expires 2026-09-01 — critical FEFO priority.", "days_remaining": 14, "severity": "HIGH"}',
    false
  )
on conflict (id) do nothing;

-- =====================================================================
-- SECTION 5: ALERTS
-- =====================================================================
insert into alerts (id, type, message, recipient, sent_at, channel) values
  (
    'dddddddd-0001-0001-0001-000000000001',
    'anomaly',
    'CRITICAL: Batch PCM-2025-A01 (Paracetamol 500mg) has two conflicting expiry dates across the supply chain. Immediate review required.',
    'State Drug Controller',
    now() - interval '2 hours',
    'dashboard'
  ),
  (
    'dddddddd-0001-0001-0001-000000000002',
    'expiry_risk',
    'ORS Sachets batch ORS-2025-C03 expires in ~14 days. Initiate FEFO recall from DISTRICT-HOSPITAL-NASHIK.',
    'District Ops',
    now() - interval '1 hour',
    'dashboard'
  ),
  (
    'dddddddd-0001-0001-0001-000000000003',
    'stockout_risk',
    'Amoxicillin 250mg forecast crosses reorder threshold in 9 days at current consumption rate.',
    'State Procurement',
    now() - interval '30 minutes',
    'dashboard'
  )
on conflict (id) do nothing;

-- =====================================================================
-- SECTION 6: FORECASTS — ML stub data for ForecastChart
-- Covers next 10 data points for Amoxicillin (drug D-002)
-- (teammate 5 will overwrite these with real model output)
-- =====================================================================
insert into forecasts (drug_id, date, predicted_stock, predicted_stockout_date, reorder_threshold) values
  ('22222222-2222-2222-2222-222222222222', current_date + 0,  5200, null,         2500),
  ('22222222-2222-2222-2222-222222222222', current_date + 3,  4900, null,         2500),
  ('22222222-2222-2222-2222-222222222222', current_date + 6,  4600, null,         2500),
  ('22222222-2222-2222-2222-222222222222', current_date + 9,  4200, null,         2500),
  ('22222222-2222-2222-2222-222222222222', current_date + 12, 3800, null,         2500),
  ('22222222-2222-2222-2222-222222222222', current_date + 15, 3300, null,         2500),
  ('22222222-2222-2222-2222-222222222222', current_date + 18, 2800, null,         2500),
  ('22222222-2222-2222-2222-222222222222', current_date + 21, 2300, null,         2500),
  ('22222222-2222-2222-2222-222222222222', current_date + 24, 1700, null,         2500),
  ('22222222-2222-2222-2222-222222222222', current_date + 27, 1100, current_date + 32, 2500)
on conflict do nothing;

-- =====================================================================
-- SECTION 7: PURCHASE ORDERS
-- NOTE: vendor_id must be a valid profiles.id, which FK-chains to
-- auth.users. If no vendor profile exists yet, skip this block —
-- re-run it after signup + profile creation. See README for steps.
-- =====================================================================
-- insert into purchase_orders (vendor_id, drug_id, quantity, status)
-- select id, '22222222-2222-2222-2222-222222222222', 5000, 'shipped'
-- from profiles where role = 'vendor' limit 1;

-- =====================================================================
-- SECTION 8: LEDGER ENTRIES — Genesis entries for clean batches
-- (teammate 3's hash-chain engine will add subsequent entries)
-- =====================================================================
insert into ledger_entries (ref_table, ref_id, data_hash, prev_hash) values
  ('batches', 'aaaaaaaa-0001-0001-0001-000000000001',
   encode(digest('PCM-2025-A01|2025-01-10|2027-01-10|Cipla Ltd', 'sha256'), 'hex'),
   null),
  ('batches', 'aaaaaaaa-0001-0001-0001-000000000002',
   encode(digest('AMX-2025-B02|2025-02-15|2027-02-15|Sun Pharma', 'sha256'), 'hex'),
   null),
  ('batches', 'aaaaaaaa-0001-0001-0001-000000000004',
   encode(digest('INS-2025-D04|2025-04-20|2026-10-20|Biocon', 'sha256'), 'hex'),
   null)
on conflict do nothing;
