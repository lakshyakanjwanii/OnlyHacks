// Single API gateway for the frontend.
// In dev: Vite proxies /api/* → localhost:8000 (no CORS issues).
// In prod: set VITE_API_BASE_URL to your deployed backend URL.
const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

// When using the Vite proxy (dev), API_BASE should be empty string so
// requests go to /api/v1/... (same-origin). If you set VITE_API_BASE_URL
// to http://localhost:8000, you'd get http://localhost:8000/api/v1/... which
// is cross-origin and relies on CORS. Leave it empty in dev for reliability.
const _base = API_BASE === "http://localhost:8000" ? "" : API_BASE;

let authToken = "";

export function setAuthToken(token) {
  authToken = token || "";
}

async function request(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {})
  };
  if (authToken) headers.Authorization = `Bearer ${authToken}`;

  const response = await fetch(`${_base}${path}`, {
    ...options,
    headers
  });

  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(body || `API request failed: ${response.status}`);
  }
  if (response.status === 204) return null;
  return response.json();
}

// useMock: true only when there is no API available at all (no VITE_API_BASE_URL
// and no Vite proxy). With the proxy configured, _base is empty string and
// fetch("/api/v1/...") goes through the proxy to the backend.
const useMock = false; // proxy always available in dev; override to true for pure offline mode

const mock = {
  drugs: [
    { id: "D-001", name: "Paracetamol 500mg", manufacturer: "CureMed Labs", gtin: "08940012345018" },
    { id: "D-002", name: "Amoxicillin 500mg", manufacturer: "NovaPharm", gtin: "08940012345025" },
    { id: "D-003", name: "Insulin Glargine", manufacturer: "BioAxis", gtin: "08940012345032" }
  ],
  batches: [
    { id: "B-2401", drug_id: "D-001", batch_number: "PCM2401A", manufacture_date: "2026-02-14", expiry_date: "2027-02-13", created_at: "2026-02-15T08:20:00Z" },
    { id: "B-2402", drug_id: "D-002", batch_number: "AMX2402B", manufacture_date: "2026-03-02", expiry_date: "2026-10-01", created_at: "2026-03-03T09:10:00Z" },
    { id: "B-2403", drug_id: "D-003", batch_number: "INS2403C", manufacture_date: "2026-04-20", expiry_date: "2026-09-18", created_at: "2026-04-21T11:40:00Z" }
  ],
  scan_events: [
    { id: "S-1", batch_id: "B-2401", node_type: "Factory", node_id: "F-MH-01", scanned_by: "system", location: { lat: 19.076, lng: 72.8777, label: "Mumbai Factory" }, timestamp: "2026-08-18T12:40:00Z", raw_payload: {} },
    { id: "S-2", batch_id: "B-2402", node_type: "District Hub", node_id: "DH-PN-04", scanned_by: "operator-14", location: { lat: 18.5204, lng: 73.8567, label: "Pune Hub" }, timestamp: "2026-08-18T11:55:00Z", raw_payload: {} },
    { id: "S-3", batch_id: "B-2403", node_type: "Hospital", node_id: "H-MUM-08", scanned_by: "pharmacist-22", location: { lat: 19.2183, lng: 72.9781, label: "Thane Hospital" }, timestamp: "2026-08-18T10:15:00Z", raw_payload: {} }
  ],
  anomalies: [
    { id: "A-101", batch_id: "B-2402", rule_triggered: "EXPIRY_CONFLICT", details: "Batch AMX2402B: conflicting expiry dates detected across scan records.", resolved: false, created_at: "2026-08-18T12:10:00Z" },
    { id: "A-102", batch_id: "B-2403", rule_triggered: "EXPIRY_SOON", details: "Insulin Glargine batch expires in 31 days.", resolved: false, created_at: "2026-08-18T09:30:00Z" },
    { id: "A-103", batch_id: "B-2401", rule_triggered: "LOCATION_MISMATCH", details: "Scan location differs from expected node route.", resolved: true, created_at: "2026-08-17T17:05:00Z" }
  ],
  purchase_orders: [
    { id: "PO-701", vendor_id: "V-01", drug_id: "D-001", quantity: 12000, status: "In Transit", created_at: "2026-08-17T08:00:00Z" },
    { id: "PO-702", vendor_id: "V-02", drug_id: "D-002", quantity: 5000, status: "Approved", created_at: "2026-08-16T10:30:00Z" }
  ],
  alerts: [
    { id: "AL-1", type: "STOCKOUT", message: "Amoxicillin forecast crosses reorder threshold in 9 days.", recipient: "District Ops", sent_at: "2026-08-18T12:00:00Z", channel: "dashboard" },
    { id: "AL-2", type: "EXPIRY", message: "Insulin Glargine batch INS2403C expires soon.", recipient: "Hospital Pharmacy", sent_at: "2026-08-18T09:31:00Z", channel: "dashboard" }
  ]
};

function mockResponse(value) {
  return Promise.resolve(JSON.parse(JSON.stringify(value)));
}

export const getDrugs = () => useMock ? mockResponse(mock.drugs) : request("/api/v1/drugs");
export const getBatches = () => useMock ? mockResponse(mock.batches) : request("/api/v1/batches");
export const getScanEvents = () => useMock ? mockResponse(mock.scan_events) : request("/api/v1/scan_events");
export const getAnomalies = () => useMock ? mockResponse(mock.anomalies) : request("/api/v1/anomalies");
export const getPurchaseOrders = () => useMock ? mockResponse(mock.purchase_orders) : request("/api/v1/purchase_orders");
export const getAlerts = () => useMock ? mockResponse(mock.alerts) : request("/api/v1/alerts");
export const getForecast = (drugId) =>
  useMock ? mockResponse({
    drug: mock.drugs.find(d => d.id === drugId)?.name || "Amoxicillin 500mg",
    dates: ["Aug 18","Aug 21","Aug 24","Aug 27","Aug 30","Sep 2","Sep 5","Sep 8","Sep 11","Sep 14"],
    predicted_stock: [5200, 4900, 4600, 4200, 3800, 3300, 2800, 2300, 1700, 1100],
    reorder_threshold: 2500
  }) : request(`/api/v1/forecast/${encodeURIComponent(drugId)}`);

export const acknowledgeAnomaly = (id) => {
  if (useMock) {
    const item = mock.anomalies.find(a => a.id === id);
    if (item) item.resolved = true;
    return mockResponse(item);
  }
  // Backend route is PATCH /api/v1/anomalies/{id}/resolve
  return request(`/api/v1/anomalies/${encodeURIComponent(id)}/resolve`, {
    method: "PATCH",
  });
};

export async function loadDashboardData() {
  const [drugs, batches, scan_events, anomalies, purchase_orders, alerts] = await Promise.all([
    getDrugs(), getBatches(), getScanEvents(), getAnomalies(), getPurchaseOrders(), getAlerts()
  ]);
  return { drugs, batches, scan_events, anomalies, purchase_orders, alerts };
}

export function getMockAuditTrail(batchId) {
  const batch = mock.batches.find(b => b.id === batchId) || mock.batches[0];
  return mockResponse([
    { timestamp: "2026-08-15T08:30:00Z", actor: "Factory Node F-MH-01", action: "BATCH_CREATED", hash: "9f1a7c…a83e", prev_hash: "GENESIS" },
    { timestamp: "2026-08-16T10:18:00Z", actor: "Scanner SC-19", action: "DISPATCH_SCAN", hash: "c2bd41…90f4", prev_hash: "9f1a7c…a83e" },
    { timestamp: "2026-08-17T13:42:00Z", actor: "District Hub DH-PN-04", action: "RECEIPT_SCAN", hash: "7a00dd…18bc", prev_hash: "c2bd41…90f4" },
    { timestamp: "2026-08-18T09:12:00Z", actor: "Validation Engine", action: "EXPIRY_VALIDATED", hash: "1ed98b…2fa1", prev_hash: "7a00dd…18bc" },
    { timestamp: "2026-08-18T12:10:00Z", actor: "Anomaly Engine", action: "ANOMALY_FLAGGED", hash: "5e9f31…c022", prev_hash: "1ed98b…2fa1" }
  ].map(x => ({ ...x, batch_id: batch.id })));
}
