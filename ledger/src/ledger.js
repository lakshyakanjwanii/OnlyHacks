const crypto = require('crypto');
const supabase = require('./supabaseClient');

/**
 * Computes the SHA-256 hash of the data combined with the previous hash.
 */
function computeHash(data, prevHash) {
  const hash = crypto.createHash('sha256');
  // Sort keys to ensure deterministic hashing for the same object
  const dataString = JSON.stringify(data, Object.keys(data).sort());
  hash.update(dataString + (prevHash || ''));
  return hash.digest('hex');
}

/**
 * Appends a new entry to the ledger.
 * @param {string} ref_table - The table this entry relates to ('batches', 'scan_events', 'anomalies').
 * @param {string|number} ref_id - The ID of the record in the ref_table.
 * @param {Object} data - The payload to hash.
 */
async function appendLedgerEntry(ref_table, ref_id, data) {
  // Fetch the last ledger entry to get the previous hash
  const { data: lastEntries, error: fetchError } = await supabase
    .from('ledger_entries')
    .select('data_hash')
    .order('created_at', { ascending: false })
    .order('id', { ascending: false })
    .limit(1);
    
  if (fetchError) throw fetchError;
  
  const prevHash = lastEntries && lastEntries.length > 0
    ? lastEntries[0].data_hash
    : 'GENESIS';

  const dataHash = computeHash(data, prevHash);

  // Insert the new ledger entry
  const { data: result, error: insertError } = await supabase
    .from('ledger_entries')
    .insert([{ ref_table, ref_id, data_hash: dataHash, prev_hash: prevHash }])
    .select();
    
  if (insertError) throw insertError;
  return result[0];
}

/**
 * Walks the ledger to verify that the chain is intact.
 * Returns { tampered: boolean, brokenLink: object | null }
 */
async function verifyChain() {
  // Fetch all ledger entries in chronological order
  const { data: entries, error } = await supabase
    .from('ledger_entries')
    .select('*')
    .order('created_at', { ascending: true })
    .order('id', { ascending: true });
    
  if (error) throw error;

  if (!entries || entries.length === 0) {
    return { tampered: false, brokenLink: null };
  }

  let expectedPrevHash = 'GENESIS';

  for (let i = 0; i < entries.length; i++) {
    const entry = entries[i];
    
    // Check if the link to the previous entry is valid
    if (entry.prev_hash !== expectedPrevHash) {
      return { 
        tampered: true, 
        brokenLink: { index: i, entry, reason: 'prev_hash mismatch' } 
      };
    }

    expectedPrevHash = entry.data_hash;
  }

  return { tampered: false, brokenLink: null };
}

module.exports = {
  appendLedgerEntry,
  verifyChain,
  computeHash
};


