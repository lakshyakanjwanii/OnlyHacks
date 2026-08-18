"""
prophet_pipeline.py — Per-drug demand forecasting + stockout prediction

For each drug:
  1. Fit Prophet on historical daily consumption (from salesdaily.csv)
  2. Forecast FORECAST_HORIZON days into the future
  3. Combine with current stock level → compute predicted_stockout_date
  4. Write results to `forecasts` table (Supabase) or return as dict

forecasts table schema:
  id, drug_id, date, predicted_stock, predicted_stockout_date, created_at
"""

'''import os
import json
import warnings
from datetime import date, datetime, timedelta
from typing import Optional
import uuid



import numpy as np
import pandas as pd
from prophet import Prophet
from supabase import create_client, Client
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://oinmewjpqvtswovyxwfb.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_clmU53HLt9W_jmd9JM2iHw_DHb2ksxX")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

warnings.filterwarnings("ignore")  # suppress Prophet/Stan noise

# ── config ───────────────────────────────────────────────────────────────────

FORECAST_HORIZON = 30        # days ahead to forecast
REORDER_THRESHOLD_DAYS = 14  # alert if stockout within this many days
CONFIDENCE_INTERVAL = 0.90

# Mock stock levels (units on hand) — replace with a DB call once backend is up
# drug_id → current_stock_units
MOCK_STOCK_LEVELS = {
    "drug_001": 850,   # Diclofenac
    "drug_002": 1200,  # Ibuprofen
    "drug_003": 300,   # Aspirin
    "drug_004": 2000,  # Paracetamol
    "drug_005": 150,   # Diazepam (low — should trigger alert)
    "drug_006": 90,    # Nitrazepam (very low)
    "drug_007": 600,   # Salbutamol
    "drug_008": 450,   # Loratadine
}


# ── Prophet wrapper ───────────────────────────────────────────────────────────

def fit_forecast(series: pd.DataFrame, horizon: int = FORECAST_HORIZON) -> dict:
    """
    Fit Prophet on a ds/y series and return forecast dict.

    Args:
        series: DataFrame with columns [ds, y] — daily consumption history
        horizon: days ahead to forecast

    Returns:
        {
          "forecast_df": pd.DataFrame with [ds, yhat, yhat_lower, yhat_upper],
          "dates": list of ISO date strings,
          "predicted_consumption": list of floats (daily),
          "avg_daily": float,
        }
    """
    if len(series) < 30:
        raise ValueError(f"Need at least 30 data points; got {len(series)}")

    # Prophet requires non-negative y
    series = series.copy()
    series["y"] = series["y"].clip(lower=0)

    model = Prophet(
        interval_width=CONFIDENCE_INTERVAL,
        daily_seasonality=False,
        weekly_seasonality=True,
        yearly_seasonality=True,
        changepoint_prior_scale=0.05,  # conservative — pharma demand is relatively stable
    )

    # Add Indian public holidays as extra regressors (demand spikes on festivals)
    model.add_country_holidays(country_name="IN")

    model.fit(series, iter=300)  # iter=300 is fast; bump to 1000 for production accuracy

    future = model.make_future_dataframe(periods=horizon, freq="D")
    forecast = model.predict(future)

    # Slice to only the future portion
    last_history_date = series["ds"].max()
    future_fc = forecast[forecast["ds"] > last_history_date].copy()
    future_fc["yhat"] = future_fc["yhat"].clip(lower=0)

    return {
        "forecast_df": future_fc[["ds", "yhat", "yhat_lower", "yhat_upper"]],
        "dates": future_fc["ds"].dt.strftime("%Y-%m-%d").tolist(),
        "predicted_consumption": future_fc["yhat"].round(2).tolist(),
        "avg_daily": float(series["y"].tail(30).mean()),
    }


def compute_stockout_date(
    current_stock: float,
    predicted_consumption: list,
    dates: list,
) -> Optional[str]:
    """
    Walk forward through predicted daily consumption until stock hits 0.
    Returns ISO date string of predicted stockout, or None if stock lasts full horizon.
    """
    stock = current_stock
    for units, day in zip(predicted_consumption, dates):
        stock -= units
        if stock <= 0:
            return day
    return None  # stock survives the full forecast window


def compute_reorder_threshold(avg_daily: float, lead_time_days: int = 7) -> float:
    """
    Reorder point = avg_daily_consumption × (lead_time + safety_buffer)
    Safety buffer = 7 days (conservative for pharma)
    """
    safety_days = 7
    return round(avg_daily * (lead_time_days + safety_days), 1)


# ── full pipeline for one drug ────────────────────────────────────────────────

def run_drug_forecast(
    drug_id: str,
    series: pd.DataFrame,
    current_stock: Optional[float] = None,
) -> dict:
    """
    Complete forecast for a single drug.
    Returns the JSON shape the frontend ForecastChart expects:
    {
      drug_id, drug_name, dates[], predicted_stock[], reorder_threshold,
      predicted_stockout_date, avg_daily_consumption, created_at
    }
    """
    if current_stock is None:
        current_stock = MOCK_STOCK_LEVELS.get(drug_id, 500)

    fc = fit_forecast(series)

    # Simulate rolling stock from today
    cumulative_consumption = list(np.cumsum(fc["predicted_consumption"]))
    predicted_stock = [max(0, current_stock - c) for c in cumulative_consumption]

    stockout_date = compute_stockout_date(
        current_stock,
        fc["predicted_consumption"],
        fc["dates"],
    )

    reorder_threshold = compute_reorder_threshold(fc["avg_daily"])

    return {
        "drug_id": drug_id,
        "dates": fc["dates"],
        "predicted_stock": [round(s, 1) for s in predicted_stock],
        "reorder_threshold": reorder_threshold,
        "predicted_stockout_date": stockout_date,
        "avg_daily_consumption": round(fc["avg_daily"], 2),
        "current_stock": current_stock,
        "created_at": datetime.utcnow().isoformat(),
    }


# ── batch pipeline: all drugs → Supabase ─────────────────────────────────────

def run_all_forecasts(long_df: pd.DataFrame) -> list[dict]:
    """
    Run forecast pipeline for all drugs in the dataset.
    Returns list of forecast result dicts.
    """
    from data.loader import get_drug_series, get_all_drug_ids, get_drug_info

    results = []
    drug_ids = get_all_drug_ids(long_df)

    for drug_id in drug_ids:
        try:
            series = get_drug_series(long_df, drug_id)
            info = get_drug_info(drug_id)
            result = run_drug_forecast(drug_id, series)
            result["drug_name"] = info.get("drug_name", drug_id)
            results.append(result)
            print(f"  ✅ {drug_id} ({info.get('drug_name','?')}) — stockout: {result['predicted_stockout_date']}")
        except Exception as e:
            print(f"  ❌ {drug_id} failed: {e}")

    return results


def write_forecasts_to_supabase(results: list[dict]) -> None:
    """
    Upsert forecast rows into the `forecasts` table.
    Schema: id, drug_id, date, predicted_stock, predicted_stockout_date, created_at
    """
    url = os.environ.get("https://oinmewjpqvtswovyxwfb.supabase.co")
    key = os.environ.get("sb_publishable_clmU53HLt9W_jmd9JM2iHw_DHb2ksxX")
    if not url or not key:
        print("⚠️  SUPABASE_URL / SUPABASE_SERVICE_KEY not set — skipping DB write")
        return

    supabase: Client = create_client(url, key)

    rows = []
    for r in results:
        for day, stock in zip(r["dates"], r["predicted_stock"]):
            rows.append({
                "drug_id": r["drug_id"],
                "date": day,
                "predicted_stock": stock,
                "predicted_stockout_date": r["predicted_stockout_date"],
                "created_at": r["created_at"],
            })

    # Upsert in batches of 500
    batch_size = 500
    for i in range(0, len(rows), batch_size):
        supabase.table("forecasts").upsert(rows[i:i+batch_size]).execute()

    print(f"✅ Wrote {len(rows)} forecast rows to Supabase")


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from data.loader import load_daily_sales

    print("Loading dataset...")
    long_df = load_daily_sales("data/salesdaily.csv")

    print("\nRunning forecasts for all drugs...")
    results = run_all_forecasts(long_df)

    

    print(f"\n{'='*50}")
    print(f"Forecast summary ({len(results)} drugs):")
    for r in results:
        flag = "🔴" if r["predicted_stockout_date"] else "🟢"
        print(f"  {flag} {r.get('drug_name','?'):15s} | stock: {r['current_stock']:>6} | stockout: {r['predicted_stockout_date'] or 'none in window'}")

    write_forecasts_to_supabase(results)'''

"""
prophet_pipeline.py — Per-drug demand forecasting + stockout prediction

For each drug:
  1. Fit Prophet on historical daily consumption (from salesdaily.csv)
  2. Forecast FORECAST_HORIZON days into the future
  3. Combine with current stock level -> compute predicted_stockout_date
  4. Write results to `forecasts` table (Supabase) or return as dict

forecasts table schema:
  id, drug_id, date, predicted_stock, predicted_stockout_date, created_at
"""

import os
import json
import warnings
from datetime import date, datetime, timedelta
from typing import Optional
import uuid
import sys
from pathlib import Path

# Add project root and ml directory to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import numpy as np
import pandas as pd
from prophet import Prophet
from supabase import create_client, Client

# Fallback directly to the provided project credentials
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://oinmewjpqvtswovyxwfb.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", " ")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

warnings.filterwarnings("ignore")  # suppress Prophet/Stan noise

# ── config ───────────────────────────────────────────────────────────────────

FORECAST_HORIZON = 30        # days ahead to forecast
REORDER_THRESHOLD_DAYS = 14  # alert if stockout within this many days
CONFIDENCE_INTERVAL = 0.90

# Mock stock levels (units on hand)
MOCK_STOCK_LEVELS = {
    "drug_001": 850,   # Diclofenac
    "drug_002": 1200,  # Ibuprofen
    "drug_003": 300,   # Aspirin
    "drug_004": 2000,  # Paracetamol
    "drug_005": 150,   # Diazepam
    "drug_006": 90,    # Nitrazepam
    "drug_007": 600,   # Salbutamol
    "drug_008": 450,   # Loratadine
}


# ── Prophet wrapper ───────────────────────────────────────────────────────────

def fit_forecast(series: pd.DataFrame, horizon: int = FORECAST_HORIZON) -> dict:
    if len(series) < 30:
        raise ValueError(f"Need at least 30 data points; got {len(series)}")

    series = series.copy()
    series["y"] = series["y"].clip(lower=0)

    model = Prophet(
        interval_width=CONFIDENCE_INTERVAL,
        daily_seasonality=False,
        weekly_seasonality=True,
        yearly_seasonality=True,
        changepoint_prior_scale=0.05,
    )

    model.add_country_holidays(country_name="IN")
    model.fit(series, iter=300)

    future = model.make_future_dataframe(periods=horizon, freq="D")
    forecast = model.predict(future)

    last_history_date = series["ds"].max()
    future_fc = forecast[forecast["ds"] > last_history_date].copy()
    future_fc["yhat"] = future_fc["yhat"].clip(lower=0)

    return {
        "forecast_df": future_fc[["ds", "yhat", "yhat_lower", "yhat_upper"]],
        "dates": future_fc["ds"].dt.strftime("%Y-%m-%d").tolist(),
        "predicted_consumption": future_fc["yhat"].round(2).tolist(),
        "avg_daily": float(series["y"].tail(30).mean()),
    }


def compute_stockout_date(
    current_stock: float,
    predicted_consumption: list,
    dates: list,
) -> Optional[str]:
    stock = current_stock
    for units, day in zip(predicted_consumption, dates):
        stock -= units
        if stock <= 0:
            return day
    return None


def compute_reorder_threshold(avg_daily: float, lead_time_days: int = 7) -> float:
    safety_days = 7
    return round(avg_daily * (lead_time_days + safety_days), 1)


# ── full pipeline for one drug ────────────────────────────────────────────────

def run_drug_forecast(
    drug_id: str,
    series: pd.DataFrame,
    current_stock: Optional[float] = None,
) -> dict:
    if current_stock is None:
        current_stock = MOCK_STOCK_LEVELS.get(drug_id, 500)

    fc = fit_forecast(series)

    cumulative_consumption = list(np.cumsum(fc["predicted_consumption"]))
    predicted_stock = [max(0, current_stock - c) for c in cumulative_consumption]

    stockout_date = compute_stockout_date(
        current_stock,
        fc["predicted_consumption"],
        fc["dates"],
    )

    reorder_threshold = compute_reorder_threshold(fc["avg_daily"])

    return {
        "drug_id": drug_id,
        "dates": fc["dates"],
        "predicted_stock": [round(s, 1) for s in predicted_stock],
        "reorder_threshold": reorder_threshold,
        "predicted_stockout_date": stockout_date,
        "avg_daily_consumption": round(fc["avg_daily"], 2),
        "current_stock": current_stock,
        "created_at": datetime.utcnow().isoformat(),
    }


# ── batch pipeline: all drugs → Supabase ─────────────────────────────────────

def run_all_forecasts(long_df: pd.DataFrame) -> list[dict]:
    try:
        from ml.data.loader import get_drug_series, get_all_drug_ids, get_drug_info
    except ModuleNotFoundError:
        from data.loader import get_drug_series, get_all_drug_ids, get_drug_info

    results = []
    drug_ids = get_all_drug_ids(long_df)

    for drug_id in drug_ids:
        try:
            series = get_drug_series(long_df, drug_id)
            info = get_drug_info(drug_id)
            result = run_drug_forecast(drug_id, series)
            result["drug_name"] = info.get("drug_name", drug_id)
            results.append(result)
            print(f"  ✅ {drug_id} ({info.get('drug_name','?')}) — stockout: {result['predicted_stockout_date']}")
        except Exception as e:
            print(f"  ❌ {drug_id} failed: {e}")

    return results


"""def write_forecasts_to_supabase(results: list[dict], batch_size: int = 100) -> None:
    
    
    if not supabase:
        print("⚠️ Supabase client not initialized — skipping DB write.")
        return

    rows = []
    for r in results:
        # Convert "drug_001" to valid UUID format expected by Postgres
        valid_drug_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, str(r["drug_id"])))

        for day, stock in zip(r["dates"], r["predicted_stock"]):
            rows.append({
                "drug_id": valid_drug_uuid,
                "date": day,
                "predicted_stock": stock,
                "predicted_stockout_date": r["predicted_stockout_date"],
                "created_at": r["created_at"],
            })

    try:
        for i in range(0, len(rows), batch_size):
            supabase.table("forecasts").upsert(rows[i:i + batch_size]).execute()
        print(f"✅ Successfully wrote {len(rows)} forecast rows to Supabase.")
    except Exception as e:
        print(f"⚠️ Supabase write error: {e}")"""

def get_or_create_drug_map(supabase_client: Client, results: list[dict]) -> dict:
    """
    Fetches real drug UUIDs from Supabase or seeds missing ones with required fields:
    name, manufacturer, and gtin.
    """
    try:
        res = supabase_client.table("drugs").select("id, name").execute()
        existing_drugs = {item["name"].strip().lower(): item["id"] for item in (res.data or []) if item.get("name")}
    except Exception as e:
        print(f"⚠️ Could not read drugs table: {e}")
        existing_drugs = {}

    drug_id_map = {}
    for idx, r in enumerate(results):
        drug_name = r.get("drug_name") or r["drug_id"]
        drug_key = drug_name.strip().lower()

        if drug_key in existing_drugs:
            drug_id_map[r["drug_id"]] = existing_drugs[drug_key]
        else:
            # Generate a valid 14-digit GTIN barcode for mock seeding
            mock_gtin = f"890123456{idx:05d}"

            try:
                insert_res = supabase_client.table("drugs").insert({
                    "name": drug_name,
                    "manufacturer": "Generic Pharma",
                    "gtin": mock_gtin,
                }).execute()
                if insert_res.data:
                    new_id = insert_res.data[0]["id"]
                    existing_drugs[drug_key] = new_id
                    drug_id_map[r["drug_id"]] = new_id
            except Exception as e:
                print(f"⚠️ Could not insert drug record for '{drug_name}': {e}")

    return drug_id_map

    
            


def write_forecasts_to_supabase(results: list[dict], batch_size: int = 100) -> None:
    """
    Upsert forecast rows linked to valid foreign key drug IDs in Supabase.
    """
    if not supabase:
        print("⚠️ Supabase client not initialized — skipping DB write.")
        return

    drug_id_map = get_or_create_drug_map(supabase, results)
    
    rows = []
    for r in results:
        real_drug_id = drug_id_map.get(r["drug_id"])
        if not real_drug_id:
            print(f"⚠️ Skipping forecast for {r.get('drug_name')} — missing valid drug_id.")
            continue

        for day, stock in zip(r["dates"], r["predicted_stock"]):
            rows.append({
                "drug_id": real_drug_id,
                "date": day,
                "predicted_stock": stock,
                "predicted_stockout_date": r["predicted_stockout_date"],
                "created_at": r["created_at"],
            })

    if not rows:
        print("⚠️ No valid rows to write.")
        return

    try:
        for i in range(0, len(rows), batch_size):
            supabase.table("forecasts").upsert(rows[i:i + batch_size]).execute()
        print(f"✅ Successfully wrote {len(rows)} forecast rows to Supabase.")
    except Exception as e:
        print(f"⚠️ Supabase write error: {e}")




# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        from ml.data.loader import load_daily_sales
    except ModuleNotFoundError:
        from data.loader import load_daily_sales

    print("Loading dataset...")
    long_df = load_daily_sales("data/salesdaily.csv")

    print("\nRunning forecasts for all drugs...")
    results = run_all_forecasts(long_df)

    print(f"\n{'='*50}")
    print(f"Forecast summary ({len(results)} drugs):")
    for r in results:
        flag = "🔴" if r["predicted_stockout_date"] else "🟢"
        print(f"  {flag} {r.get('drug_name','?'):15s} | stock: {r['current_stock']:>6} | stockout: {r['predicted_stockout_date'] or 'none in window'}")

    write_forecasts_to_supabase(results)