// scanner/src/conflictDetector.js

// In-memory store of scans seen this session, keyed by GTIN + batch together.
// This resets when the page is refreshed.
const seenRecords = new Map();

/**
 * Compares a newly scanned barcode against a previous scan
 * with the same GTIN + batch number.
 *
 * First scan of this GTIN+batch combo:
 *   → new
 *
 * Same GTIN + same batch + same expiry:
 *   → clean
 *
 * Same GTIN + same batch, but expiry differs from what was
 * previously seen for this GTIN+batch:
 *   → conflict
 */
export function detectConflict(parsed) {
  if (!parsed.gtin || !parsed.batchNumber) {
    return {
      status: 'new',
      message: 'Cannot check for conflicts — missing GTIN or batch.',
      previous: null,
    };
  }

  const key = `${parsed.gtin}::${parsed.batchNumber}`;
  const previous = seenRecords.get(key);

  // First scan of this GTIN+batch combo
  if (!previous) {
    seenRecords.set(key, parsed);

    return {
      status: 'new',
      message: 'First scan of this GTIN + batch — recorded as baseline.',
      previous: null,
    };
  }

  const expiryDiffers = previous.expiryDate !== parsed.expiryDate;

  // Same GTIN + same batch, but expiry differs from baseline
  if (expiryDiffers) {
    return {
      status: 'conflict',
      message: `⚠️ CONFLICT: batch "${parsed.batchNumber}" previously had expiry "${previous.expiryDate}", now "${parsed.expiryDate}".`,
      previous,
    };
  }

  // Same GTIN, same batch, same expiry
  return {
    status: 'clean',
    message: '✅ Matches previously scanned data for this batch.',
    previous,
  };
}

/**
 * Clears the current session's scan history.
 */
export function resetScanHistory() {
  seenRecords.clear();
}