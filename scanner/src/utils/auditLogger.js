const STORAGE_KEY = 'gs1_scan_audit_log';

/**
 * Retrieves all stored scan logs from localStorage.
 * @returns {Array} List of scan log entries
 */
export function getAuditLogs() {
  try {
    const data = localStorage.getItem(STORAGE_KEY);
    return data ? JSON.parse(data) : [];
  } catch (err) {
    console.error('Failed to read audit logs:', err);
    return [];
  }
}

/**
 * Appends a new scan entry to the audit log.
 * @param {Object} parsed - Parsed GS1 barcode data from parseGS1()
 * @param {Object} conflictResult - Conflict status result from conflictDetector
 * @returns {Array} Updated list of scan log entries
 */
export function logScan(parsed, conflictResult) {
  const newEntry = {
    id: `scan_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`,
    timestamp: new Date().toISOString(),
    gtin: parsed.gtin || 'N/A',
    batchNumber: parsed.batchNumber || 'N/A',
    expiryDate: parsed.expiryDate || 'N/A',
    mfdDate: parsed.mfdDate || 'N/A',
    serial: parsed.serial || 'N/A',
    status: conflictResult?.status || 'unknown',
    message: conflictResult?.message || '',
    rawPayload: parsed.rawPayload || '',
  };

  const currentLogs = getAuditLogs();
  const updatedLogs = [newEntry, ...currentLogs];

  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updatedLogs));
  } catch (err) {
    console.error('Failed to save audit log:', err);
  }

  return updatedLogs;
}

/**
 * Clears all audit logs from storage.
 */
export function clearAuditLogs() {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch (err) {
    console.error('Failed to clear audit logs:', err);
  }
  return [];
}

/**
 * Exports audit logs as a downloadable CSV file.
 */
export function exportLogsToCSV() {
  const logs = getAuditLogs();
  if (logs.length === 0) return alert('No logs available to export.');

  const headers = ['Timestamp', 'Status', 'GTIN', 'Batch Number', 'Expiry Date', 'Serial', 'Message', 'Raw Payload'];
  const rows = logs.map(log => [
    `"${log.timestamp}"`,
    `"${log.status}"`,
    `"${log.gtin}"`,
    `"${log.batchNumber}"`,
    `"${log.expiryDate}"`,
    `"${log.serial}"`,
    `"${(log.message || '').replace(/"/g, '""')}"`,
    `"${(log.rawPayload || '').replace(/"/g, '""')}"`,
  ]);

  const csvContent = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);

  const link = document.createElement('a');
  link.setAttribute('href', url);
  link.setAttribute('download', `gs1_scan_audit_log_${new Date().toISOString().slice(0, 10)}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}