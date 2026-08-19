import { exportLogsToCSV } from '../utils/auditLogger';

const STATUS_STYLES = {
  new: { label: 'New', bg: '#1e3a5f', color: '#7dd3fc' },
  clean: { label: '✅ Clean', bg: '#14532d', color: '#86efac' },
  conflict: { label: '⚠️ Conflict', bg: '#7f1d1d', color: '#fca5a5' },
  'unknown-barcode': { label: 'Unknown', bg: '#44403c', color: '#d6d3d1' },
};

function StatusBadge({ status }) {
  const style = STATUS_STYLES[status] || STATUS_STYLES.new;
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '2px 8px',
        borderRadius: '999px',
        fontSize: '0.75rem',
        fontWeight: 600,
        backgroundColor: style.bg,
        color: style.color,
      }}
    >
      {style.label}
    </span>
  );
}

export function AuditLogView({ logs, onClearHistory }) {
  return (
    <div className="audit-log-section">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h3 style={{ margin: 0, color: '#f8fafc' }}>Audit Log & History</h3>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button className="btn" onClick={() => exportLogsToCSV(logs)} disabled={logs.length === 0}>
            📥 Export CSV
          </button>
        </div>
      </div>

      {logs.length === 0 ? (
        <p style={{ color: '#94a3b8', fontStyle: 'italic', margin: 0 }}>
          No scans recorded in history yet.
        </p>
      ) : (
        <div className="audit-table-wrapper">
          <table className="audit-table">
            <thead>
              <tr>
                <th>GTIN</th>
                <th>Lot / Batch</th>
                <th>Expiry</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr
                  key={log.id}
                  style={log.status === 'conflict' ? { backgroundColor: 'rgba(127, 29, 29, 0.15)' } : undefined}
                >
                  <td>{log.gtin || 'N/A'}</td>
                  <td>{log.batchNumber || 'N/A'}</td>
                  <td>{log.expiryDate || 'N/A'}</td>
                  <td><StatusBadge status={log.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}