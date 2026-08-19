"""
main.py — FastAPI ML service
Runs on port 8000

Endpoints:
  GET  /                             → root status & docs link
  GET  /health                       → health check & dataset status
  GET  /forecast/{drug_id}           → JSON forecast for frontend ForecastChart
  POST /run-pipeline                 → trigger full forecast + alert pipeline
  GET  /expiry-risk                  → all batches flagged for expiry risk
  GET  /drugs                        → list available drug IDs
"""

import os
import sys
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Make sure project root is on path when running as: uvicorn api.main:app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.loader import load_daily_sales, get_drug_series, get_all_drug_ids, get_drug_info
from forecasting.prophet_pipeline import run_drug_forecast, run_all_forecasts, write_forecasts_to_supabase
from forecasting.expiry_risk import scan_all_batches_for_expiry_risk
from alerts.notify import check_and_fire_stockout_alerts, subscribe_anomalies_realtime


# ── app state ─────────────────────────────────────────────────────────────────

_long_df: Optional[pd.DataFrame] = None   # loaded once at startup
_forecast_cache: dict = {}                # drug_id → forecast result


def _get_dataset() -> pd.DataFrame:
    global _long_df
    if _long_df is None:
        data_path = os.environ.get("DATASET_PATH", "data/salesdaily.csv")
        _long_df = load_daily_sales(data_path)
    return _long_df


# ── lifespan: load data + optional realtime sub on startup ───────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[ML] Service starting -- loading dataset...")
    try:
        _get_dataset()
        print("[ML] Dataset loaded OK")
    except FileNotFoundError as e:
        print(f"[ML] WARNING: {e}")
        print("    Service will start but /forecast endpoints won't work until dataset is placed.")

    # Subscribe to Supabase anomalies in background thread (non-blocking)
    if os.environ.get("ENABLE_REALTIME_ALERTS", "false").lower() == "true":
        import threading
        threading.Thread(target=subscribe_anomalies_realtime, daemon=True).start()
        print("[ML] Anomaly realtime subscription started")

    yield
    print("[ML] Service shutting down")


# ── app ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Drug Supply Chain — ML Service",
    description="Forecasting, expiry risk, and alert pipeline for SIH PSS04",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in production; backend will proxy anyway
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── response models ───────────────────────────────────────────────────────────

class ForecastResponse(BaseModel):
    drug_id: str
    drug_name: str
    drug: str = ""         # alias kept for frontend ForecastChart compatibility
    dates: list[str]
    predicted_stock: list[float]
    reorder_threshold: float
    predicted_stockout_date: Optional[str]
    avg_daily_consumption: float
    current_stock: float
    created_at: str

class DrugInfo(BaseModel):
    drug_id: str
    drug_name: str
    atc_code: str

class PipelineResult(BaseModel):
    drugs_processed: int
    stockout_alerts_fired: int
    expiry_batches_flagged: int
    timestamp: str


# ── endpoints ─────────────────────────────────────────────────────────────────

@app.get("/")
def read_root():
    """Root status endpoint providing basic service health and documentation links."""
    return {
        "status": "online",
        "service": "Drug Supply Chain — ML Service",
        "docs_url": "/docs",
        "health_url": "/health"
    }


@app.get("/health")
def health():
    dataset_loaded = _long_df is not None
    return {
        "status": "ok",
        "dataset_loaded": dataset_loaded,
        "drugs_available": len(get_all_drug_ids(_long_df)) if dataset_loaded else 0,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/drugs", response_model=list[DrugInfo])
def list_drugs():
    """List all available drug IDs (from dataset)."""
    df = _get_dataset()
    result = []
    for did in get_all_drug_ids(df):
        info = get_drug_info(did)
        result.append(DrugInfo(
            drug_id=did,
            drug_name=info.get("drug_name", did),
            atc_code=info.get("atc_code", ""),
        ))
    return result


@app.get("/forecast/{drug_id}", response_model=ForecastResponse)
def get_forecast(
    drug_id: str,
    refresh: bool = Query(False, description="Force re-run Prophet model (slower)"),
    current_stock: Optional[float] = Query(None, description="Override current stock level"),
):
    """
    Get demand forecast for a specific drug.

    Returns exactly the shape the frontend ForecastChart component expects:
    { drug, dates[], predicted_stock[], reorder_threshold, predicted_stockout_date }
    """
    # Serve from cache unless refresh requested
    if not refresh and drug_id in _forecast_cache:
        result = _forecast_cache[drug_id]
        if current_stock is not None:
            # quick recalc without refitting if stock changes
            result = _adjust_stock(result, current_stock)
        return ForecastResponse(**result)

    df = _get_dataset()
    try:
        series = get_drug_series(df, drug_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Drug '{drug_id}' not found")

    info = get_drug_info(drug_id)

    try:
        result = run_drug_forecast(drug_id, series, current_stock=current_stock)
        result["drug_name"] = info.get("drug_name", drug_id)
        result["drug"] = result["drug_name"]  # frontend ForecastChart reads forecast.drug
        _forecast_cache[drug_id] = result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Forecasting failed: {str(e)}")

    return ForecastResponse(**result)


@app.post("/run-pipeline", response_model=PipelineResult)
async def run_full_pipeline(background_tasks: BackgroundTasks):
    """
    Trigger full forecast pipeline:
      1. Forecast all drugs
      2. Write to forecasts table
      3. Scan batches for expiry risk → write to anomalies
      4. Fire stockout alerts via WhatsApp/SMS

    Runs synchronously (for hackathon demo; use Celery/ARQ for production).
    """
    df = _get_dataset()

    # 1. Forecast all drugs
    results = run_all_forecasts(df)
    for r in results:
        r["drug"] = r.get("drug_name", r["drug_id"])
    _forecast_cache.update({r["drug_id"]: r for r in results})

    # 2. Write to DB
    background_tasks.add_task(write_forecasts_to_supabase, results)

    # 3. Expiry risk scan
    expiry_flagged = scan_all_batches_for_expiry_risk(results)

    # 4. Fire expiry risk alerts
    # NOTE: alert_expiry_risk is a plain async def; asyncio.coroutine() was
    # removed in Python 3.11. Use background_tasks.add_task directly.
    if expiry_flagged:
        from alerts.notify import alert_expiry_risk
        for batch in expiry_flagged:
            background_tasks.add_task(
                alert_expiry_risk,
                drug_name=batch.get("drug_name", batch["drug_id"]),
                batch_id=batch["batch_id"],
                units_at_risk=batch["units_at_risk"],
                expiry_date=batch.get("expiry_date", "unknown"),
            )

    # 5. Fire stockout alerts
    background_tasks.add_task(check_and_fire_stockout_alerts, results)

    return PipelineResult(
        drugs_processed=len(results),
        stockout_alerts_fired=sum(
            1 for r in results
            if r.get("predicted_stockout_date")
        ),
        expiry_batches_flagged=len(expiry_flagged),
        timestamp=datetime.utcnow().isoformat(),
    )


@app.get("/expiry-risk")
def get_expiry_risk():
    """
    Return expiry risk assessment for all batches.
    Uses cached forecast results for consumption rates.
    """
    if not _forecast_cache:
        raise HTTPException(
            status_code=425,
            detail="Run /run-pipeline first to populate forecast cache"
        )
    flagged = scan_all_batches_for_expiry_risk(list(_forecast_cache.values()))
    return {"flagged_batches": len(flagged), "batches": flagged}


# ── helpers ───────────────────────────────────────────────────────────────────

def _adjust_stock(result: dict, new_stock: float) -> dict:
    """Quick recalculation of predicted_stock with a different starting stock level."""
    import numpy as np
    from forecasting.prophet_pipeline import compute_stockout_date

    avg = result["avg_daily_consumption"]
    n = len(result["dates"])
    consumption = [avg] * n
    cumulative = list(np.cumsum(consumption))
    result = result.copy()
    result["predicted_stock"] = [round(max(0, new_stock - c), 1) for c in cumulative]
    result["current_stock"] = new_stock
    result["predicted_stockout_date"] = compute_stockout_date(new_stock, consumption, result["dates"])
    return result


# ── dev entrypoint ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8001, reload=True)