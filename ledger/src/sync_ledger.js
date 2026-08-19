const { checkBatch, checkScan } = require('./anomaly_engine');
const { verifyChain } = require('./ledger');
const supabase = require('./supabaseClient');

async function clearLedger() {
  console.log("Clearing existing ledger_entries and anomalies...");
  
  // Empty ledger_entries
  const { error: leError } = await supabase
    .from('ledger_entries')
    .delete()
    .not('id', 'is', null);

  if (leError) {
    console.error("Failed to clear ledger_entries:", leError);
  }

  // Empty anomalies
  const { error: anError } = await supabase
    .from('anomalies')
    .delete()
    .not('id', 'is', null);
    
  if (anError) {
    console.error("Failed to clear anomalies:", anError);
  }
}

async function syncBatches() {
  console.log("Fetching batches...");
  const { data: batches, error } = await supabase
    .from('batches')
    .select('*')
    .order('created_at', { ascending: true });

  if (error) {
    console.error("Error fetching batches:", error);
    return;
  }

  console.log(`Processing ${batches.length} batches through anomaly engine & ledger...`);
  for (const batch of batches) {
    await checkBatch(batch);
  }
  console.log("Batches synchronized.");
}

async function syncScans() {
  console.log("Fetching scan events...");
  const { data: scans, error } = await supabase
    .from('scan_events')
    .select('*')
    .order('timestamp', { ascending: true });

  if (error) {
    console.error("Error fetching scan_events:", error);
    return;
  }

  console.log(`Processing ${scans.length} scan events through anomaly engine & ledger...`);
  for (const scan of scans) {
    await checkScan(scan);
  }
  console.log("Scan events synchronized.");
}

async function runSync() {
  console.log("Starting deterministic ledger sync...");
  await clearLedger();
  await syncBatches();
  await syncScans();

  console.log("Verifying cryptographic hash chain...");
  const result = await verifyChain();
  if (result.tampered) {
    console.error("❌ Chain verification FAILED:", result.brokenLink);
  } else {
    console.log("✅ Chain verification PASSED. Cryptographic integrity is intact.");
  }
}

if (require.main === module) {
  runSync().catch(console.error);
}
