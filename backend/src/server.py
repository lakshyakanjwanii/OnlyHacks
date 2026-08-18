from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.routes import drugs, batches, scan_events, purchase_orders, anomalies, alerts, forecast, keys

app = FastAPI(
    title="Drug Supply Chain Control Tower — Backend API",
    description="PSS04 · Smart India Hackathon. Thin API layer over Supabase Postgres + Auth.",
    version="1.0.0",
)

# NOTE: tighten allow_origins to the deployed frontend URL before the
# live demo — wide open for local dev across all 5 team members' machines.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    return {"status": "ok", "service": "backend"}
