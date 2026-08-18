from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.routes import drugs, batches, scan_events, purchase_orders, anomalies, alerts, forecast, keys

app = FastAPI(
    title="Drug Supply Chain Control Tower — Backend API",
    description="PSS04 · Smart India Hackathon. Thin API layer over Supabase Postgres + Auth.",
    version="1.0.0",
)

import os

FRONTEND_URL = os.getenv("FRONTEND_URL")
ENV = os.getenv("ENV", "development")

_local_origins = ["http://localhost:5173", "http://127.0.0.1:5173",
                   "http://localhost:5174", "http://127.0.0.1:5174"]  # Vite fallback port

if ENV == "production":
    if not FRONTEND_URL:
        raise RuntimeError(
            "ENV=production but FRONTEND_URL is not set — refusing to start "
            "with no valid CORS origin. Set FRONTEND_URL in your .env."
        )
    allow_origins = [FRONTEND_URL]
else:
    allow_origins = _local_origins + ([FRONTEND_URL] if FRONTEND_URL else [])

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)

app.include_router(drugs.router)
app.include_router(batches.router)
app.include_router(scan_events.router)
app.include_router(purchase_orders.router)
app.include_router(anomalies.router)
app.include_router(alerts.router)
app.include_router(forecast.router)
app.include_router(keys.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "backend", "env": ENV, "cors_origins": allow_origins}