const { appendLedgerEntry } = require('./ledger');
const supabase = require('./supabaseClient');

/**
 * Helper to log anomaly and record it in the ledger.
 */
async function flagAnomaly(batch_id, rule_triggered, details) {
  const { data, error } = await supabase
    .from('anomalies')
    .insert([{
      batch_id,
      rule_triggered,
      details,
      resolved: false
    }])
    .select();

  if (error) throw error;
  const anomaly = data[0];

  // Append anomaly flag to ledger for tamper-evident tracking
  await appendLedgerEntry('anomalies', anomaly.id, anomaly);
  return anomaly;
}

/**
 * Rule Engine: Validates Batch inserts/updates
 * a. Batch-expiry consistency (CAG Audit Bug)
 * b. Chronology check
 */
async function checkBatch(batchData) {
  const anomalies = [];

  // RULE a: Batch-expiry consistency (CAG Audit Bug)
  // Check if same drug_id and batch_number exists with a DIFFERENT expiry_date
  const { data: existingBatches, error } = await supabase
    .from('batches')
    .select('id, expiry_date')
    .eq('drug_id', batchData.drug_id)
    .eq('batch_number', batchData.batch_number)
    .neq('id', batchData.id || 0);

  if (error) throw error;
  
  if (existingBatches && existingBatches.length > 0) {
    for (const existing of existingBatches) {
      if (new Date(existing.expiry_date).getTime() !== new Date(batchData.expiry_date).getTime()) {
        const anomaly = await flagAnomaly(batchData.id || existing.id, 'BATCH_EXPIRY_MISMATCH', {
          msg: 'CAG Audit Bug Caught: Same batch number exists with conflicting expiry date.',
          drug_id: batchData.drug_id,
          batch_number: batchData.batch_number,
          new_expiry: batchData.expiry_date,
          existing_expiry: existing.expiry_date
        });
        anomalies.push(anomaly);
        break; // Only flag once per batch validation
      }
    }
  }

  // RULE b: Chronology check
  const mfgDate = new Date(batchData.manufacture_date);
  const expDate = new Date(batchData.expiry_date);
  const now = new Date();

  if (expDate <= mfgDate) {
    const anomaly = await flagAnomaly(batchData.id, 'CHRONOLOGY_ERROR', {
      msg: 'Expiry date is before or equal to manufacture date.',
      manufacture_date: batchData.manufacture_date,
      expiry_date: batchData.expiry_date
    });
    anomalies.push(anomaly);
  } else if (mfgDate > now) {
    const anomaly = await flagAnomaly(batchData.id, 'CHRONOLOGY_ERROR', {
      msg: 'Manufacture date is in the future.',
      manufacture_date: batchData.manufacture_date
    });
    anomalies.push(anomaly);
  }

  // Log batch to ledger
  if (batchData.id) {
    await appendLedgerEntry('batches', batchData.id, batchData);
  }

  return anomalies;
}

/**
 * Rule Engine: Validates Scan Events
 * c. Barcode-PO mismatch
 * d. Cold-chain breach
 * e. Duplicate entry
 */
async function checkScan(scanData) {
  const anomalies = [];

  // Fetch the batch associated with this scan
  const { data: batchResult } = await supabase
    .from('batches')
    .select('drug_id')
    .eq('id', scanData.batch_id)
    .limit(1);

  const drugId = batchResult && batchResult.length > 0 ? batchResult[0].drug_id : null;

  if (!drugId) {
    const anomaly = await flagAnomaly(scanData.batch_id, 'UNKNOWN_BATCH', {
      msg: 'Scan event references an unknown batch ID.'
    });
    anomalies.push(anomaly);
  } else {
    // RULE c: Barcode-PO mismatch
    if (scanData.vendor_id) {
      const { data: poResult } = await supabase
        .from('purchase_orders')
        .select('id')
        .eq('drug_id', drugId)
        .eq('vendor_id', scanData.vendor_id)
        .eq('status', 'OPEN');
        
      if (!poResult || poResult.length === 0) {
        const anomaly = await flagAnomaly(scanData.batch_id, 'PO_MISMATCH', {
          msg: 'No open purchase order found for this drug and vendor.',
          drug_id: drugId,
          vendor_id: scanData.vendor_id
        });
        anomalies.push(anomaly);
      }
    }
  }

  // RULE d: Cold-chain breach
  try {
    const payload = typeof scanData.raw_payload === 'string' ? JSON.parse(scanData.raw_payload) : (scanData.raw_payload || {});
    if (payload.temperature !== undefined) {
      const temp = parseFloat(payload.temperature);
      if (temp < 2 || temp > 8) {
        const anomaly = await flagAnomaly(scanData.batch_id, 'COLD_CHAIN_BREACH', {
          msg: 'Temperature reading outside acceptable 2-8°C range.',
          reading: temp
        });
        anomalies.push(anomaly);
      }
    }
  } catch (e) {
    // Parsing error for payload
  }

  // RULE e: Duplicate entry
  // Same batch_id + node_id scanned twice in a short window (e.g. 5 minutes)
  const { data: windowResult } = await supabase
    .from('scan_events')
    .select('id, timestamp')
    .eq('batch_id', scanData.batch_id)
    .eq('node_id', scanData.node_id)
    .neq('id', scanData.id || 0)
    .order('timestamp', { ascending: false })
    .limit(1);

  if (windowResult && windowResult.length > 0) {
    const lastScanTime = new Date(windowResult[0].timestamp).getTime();
    const currentScanTime = new Date(scanData.timestamp).getTime();
    const timeDiffMinutes = (currentScanTime - lastScanTime) / (1000 * 60);

    if (Math.abs(timeDiffMinutes) < 5) {
      const anomaly = await flagAnomaly(scanData.batch_id, 'DUPLICATE_SCAN', {
        msg: 'Same batch scanned at the same node within 5 minutes.',
        timeDiffMinutes
      });
      anomalies.push(anomaly);
    }
  }

  // Log scan event to ledger
  if (scanData.id) {
    await appendLedgerEntry('scan_events', scanData.id, scanData);
  }

  return anomalies;
}

module.exports = {
  checkBatch,
  checkScan,
  flagAnomaly
};
