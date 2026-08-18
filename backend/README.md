# Backend — Drug Supply Chain Control Tower (PSS04)

FastAPI thin layer over Supabase Postgres + Auth + Row Level Security.

## Local setup

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # fill in your Supabase project values
```

## Apply the schema

In the Supabase Dashboard → SQL Editor, run in this order:
1. `migrations/001_init_schema.sql`
2. `policies/002_rls_policies.sql`
3. `seed/seed.sql` (after at least one `vendor`-role profile exists, or comment out the PO insert)

Or via Supabase CLI:
```bash
supabase link --project-ref <your-project-ref>
supabase db push
```

## Run locally

```bash
uvicorn src.server:app --reload --port 8000
```
API docs auto-generate at `http://localhost:8000/docs`.

## Routes

| Method | Path | Notes |
|---|---|---|
| GET/POST | `/api/v1/drugs` | |
| GET | `/api/v1/batches`, `/api/v1/batches/{id}` | |
| POST | `/api/v1/batches` | anomaly engine catches conflicts post-insert |
| GET | `/api/v1/batches/{id}/audit-trail` | reads `ledger_entries` |
| GET/POST | `/api/v1/scan_events` | dual auth: JWT or `X-API-Key` |
| GET/POST/PATCH | `/api/v1/purchase_orders` | |
| GET/PATCH | `/api/v1/anomalies` | writes owned by `/ledger` service |
| GET | `/api/v1/alerts` | |
| GET | `/api/v1/forecast/{drug_id}` | proxies `forecasts` table written by `/ml` |
| POST | `/api/v1/keys` | admin-only (state role), returns raw key once |
| PATCH | `/api/v1/keys/{id}/revoke` | |

## Auth model

- **Dashboard users** (frontend): Supabase JWT in `Authorization: Bearer <token>` → RLS applies automatically via `client_for_request()`.
- **External/vendor systems**: `X-API-Key: <raw key>` header → validated against `api_keys.key_hash`, scoped by the `scopes[]` array. Currently wired on `POST /scan_events`; extend the same pattern to other routes as needed.

## Deploy (Render/Railway)

Both read the included `Dockerfile` directly — just set the env vars from `.env.example` in the service's dashboard and deploy. No other config needed.

## For teammates

- **Teammate 3 (ledger/anomaly engine)**: hook into `POST /batches` and `POST /scan_events` — either via a Postgres trigger you add in your own migration file, or by subscribing to Supabase Realtime on those tables. Write results to `anomalies` and `ledger_entries` using the `supabase_admin` (service_role) client — RLS blocks direct writes from a normal session.
- **Teammate 5 (ML)**: write your forecast output into the `forecasts` table (`drug_id, date, predicted_stock, predicted_stockout_date, reorder_threshold`) — `GET /forecast/{drug_id}` reads it and reshapes it for the frontend automatically. No need to expose your own HTTP endpoint unless you prefer that; swap the read in `routes/forecast.py` for an `httpx` call if so.
- **Teammate 1 (frontend)**: point `VITE_API_BASE_URL` at this service. All response shapes match `CONTRACT.md`.
