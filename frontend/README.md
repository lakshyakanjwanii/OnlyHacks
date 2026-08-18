# Pharma Tower — Frontend

React + Tailwind + Recharts + Leaflet frontend for the SIH PSS04 Drug Supply Chain Control Tower.

## Run

```bash
cd frontend
npm install
npm run dev
```

Production build:

```bash
npm run build
```

## Backend integration

Copy `.env.example` to `.env` and set:

```env
VITE_API_BASE_URL=https://your-api.example.com
```

All API access is centralized in `src/api.js`.

Expected endpoints:

- GET `/api/v1/drugs`
- GET `/api/v1/batches`
- GET `/api/v1/scan_events`
- GET `/api/v1/anomalies`
- GET `/api/v1/purchase_orders`
- GET `/api/v1/alerts`
- GET `/api/v1/forecast/:drug_id`

JWT is sent as `Authorization: Bearer <token>` after calling `setAuthToken(token)`.

With no `VITE_API_BASE_URL`, the UI automatically uses safe mock responses in `api.js`, so the dashboard can be demonstrated before the backend is deployed.

## Notes

- Leaflet uses OpenStreetMap tiles.
- Forecast chart consumes `{ drug, dates[], predicted_stock[], reorder_threshold }`.
- Role selector changes the dashboard shell/context without coupling the UI to backend authorization logic.
- The audit trail component is ready to consume the ledger team's `{ timestamp, actor, action, hash, prev_hash }` shape.
