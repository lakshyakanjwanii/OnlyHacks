"""
prophet_pipeline.py -- Per-drug demand forecasting + stockout prediction

For each drug:
  1. Fit Prophet on historical daily consumption (from salesdaily.csv)
  2. Forecast FORECAST_HORIZON days into the future
  3. Combine with current stock level -> compute predicted_stockout_date
  4. Write results to `forecasts` table (Supabase) or return as dict

forecasts table schema:
  id, drug_id, date, predicted_stock, predicted_stockout_date, reorder_threshold, created_at
"""

import os
import warnings
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
import uuid

# Add ml/ directory to Python path so imports work whether invoked as
#   uvicorn api.main:app   (CWD = ml/)
#   python forecasting/prophet_pipeline.py   (CWD = ml/)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import numpy as np
import pandas as pd
from prophet import Prophet
from dotenv import load_dotenv
from supabase import create_client, Client

# Load env variables from backend/.env
load_dotenv(str(Path(__file__).resolve().parent.parent.parent / "backend" / ".env"))

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", os.getenv("SUPABASE_KEY"))

if not SUPABASE_URL or not SUPABASE_KEY:
    print("   SUPABASE_URL or SUPABASE_KEY missing. DB writes will be skipped.", file=sys.stderr)

# ---- Monkey-patch for modern Supabase keys ----------------------------------
# supabase-py validates keys against a JWT regex and rejects modern sb_...
# keys. We patch the regex matcher in the sync client to bypass this check.
import re
import supabase._sync.client as _sb_sync_client

_original_re_match = re.match


def _bypass_jwt_key_check(pattern, string, *args, **kwargs):
    pat_str = getattr(pattern, "pattern", pattern)
    if (
        isinstance(pat_str, str)
        and "A-Za-z0-9-_=" in pat_str
        and isinstance(string, str)
        and string.startswith("sb_")
    ):
        return True  # accept modern Supabase publishable/service keys
    return _original_re_match(pattern, string, *args, **kwargs)


_sb_sync_client.re.match = _bypass_jwt_key_check
# -----------------------------------------------------------------------------

_supabase_client: Optional[Client] = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as _e:
        print(f"   Could not create Supabase client: {_e}", file=sys.stderr)

warnings.filterwarnings("ignore")  # suppress Prophet/Stan noise

# ---- Config -----------------------------------------------------------------

FORECAST_HORIZON = 30         # days ahead to forecast
REORDER_THRESHOLD_DAYS = 14   # alert if stockout within this many days
CONFIDENCE_INTERVAL = 0.90

# Mock stock levels (units on hand) keyed by drug_id.
# Import MOCK_DRUG_IDS lazily to avoid circular-import issues at module load.
try:
    from data.loader import MOCK_DRUG_IDS as _MOCK_IDS
except ImportError:
    from ml.data.loader import MOCK_DRUG_IDS as _MOCK_IDS

MOCK_STOCK_LEVELS: dict = {
    _MOCK_IDS["M01AB"]: 850,    # Diclofenac
    _MOCK_IDS["M01AE"]: 1200,   # Ibuprofen
    _MOCK_IDS["N02BA"]: 300,    # Aspirin
    _MOCK_IDS["N02BE"]: 2000,   # Paracetamol
    _MOCK_IDS["N05B"]:  150,    # Diazepam
    _MOCK_IDS["N05C"]:  90,     # Nitrazepam
    _MOCK_IDS["R03"]:   600,    # Salbutamol
    _MOCK_IDS["R06"]:   450,    # Loratadine
}


# ---- Prophet wrapper --------------------------------------------------------

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


# ---- Full pipeline for one drug ---------------------------------------------

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


# ---- Batch pipeline: all drugs -> Supabase ----------------------------------

def run_all_forecasts(long_df: pd.DataFrame) -> list:
    try:
        from data.loader import get_drug_series, get_all_drug_ids, get_drug_info
    except ImportError:
        from ml.data.loader import get_drug_series, get_all_drug_ids, get_drug_info

    results = []
    drug_ids = get_all_drug_ids(long_df)

    for drug_id in drug_ids:
        try:
            series = get_drug_series(long_df, drug_id)
            info = get_drug_info(drug_id)
            result = run_drug_forecast(drug_id, series)
            result["drug_name"] = info.get("drug_name", drug_id)
            results.append(result)
            print(f"  {drug_id} ({info.get('drug_name', '?')}) -- stockout: {result['predicted_stockout_date']}")
        except Exception as exc:
            print(f"  {drug_id} failed: {exc}")

    return results


def get_or_create_drug_map(supabase_client: Client, results: list) -> dict:
    """
    Fetches real drug UUIDs from Supabase matched by drug name (case-insensitive).
    If a drug is not found, inserts a new record with a unique GTIN.
    Returns {ml_drug_id -> real_supabase_uuid}.
    """
    try:
        res = supabase_client.table("drugs").select("id, name").execute()
        existing_drugs = {
            item["name"].strip().lower(): item["id"]
            for item in (res.data or [])
            if item.get("name")
        }
    except Exception as exc:
        print(f"   Could not read drugs table: {exc}")
        existing_drugs = {}

    drug_id_map: dict = {}
    for idx, r in enumerate(results):
        drug_name = r.get("drug_name") or r["drug_id"]
        drug_key = drug_name.strip().lower()

        if drug_key in existing_drugs:
            drug_id_map[r["drug_id"]] = existing_drugs[drug_key]
        else:
            # Generate a unique 14-digit GTIN placeholder
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
            except Exception as exc:
                print(f"   Could not insert drug record for '{drug_name}': {exc}")

    return drug_id_map


def write_forecasts_to_supabase(results: list, batch_size: int = 100) -> None:
    """
    Upsert forecast rows linked to valid foreign-key drug IDs in Supabase.
    """
    if not _supabase_client:
        print("   Supabase client not initialised -- skipping DB write.")
        return

    drug_id_map = get_or_create_drug_map(_supabase_client, results)

    rows = []
    for r in results:
        real_drug_id = drug_id_map.get(r["drug_id"])
        if not real_drug_id:
            print(f"   Skipping forecast for {r.get('drug_name')} -- missing valid drug_id.")
            continue

        for day, stock in zip(r["dates"], r["predicted_stock"]):
            rows.append({
                "drug_id": real_drug_id,
                "date": day,
                "predicted_stock": stock,
                "predicted_stockout_date": r["predicted_stockout_date"],
                "reorder_threshold": r.get("reorder_threshold"),
                "created_at": r["created_at"],
            })

    if not rows:
        print("   No valid rows to write.")
        return

    try:
        for i in range(0, len(rows), batch_size):
            _supabase_client.table("forecasts").upsert(rows[i:i + batch_size]).execute()
        print(f"Successfully wrote {len(rows)} forecast rows to Supabase.")
    except Exception as exc:
        print(f"   Supabase write error: {exc}")


# ---- CLI entry point --------------------------------------------------------

if __name__ == "__main__":
    try:
        from data.loader import load_daily_sales
    except ImportError:
        from ml.data.loader import load_daily_sales

    print("Loading dataset...")
    long_df = load_daily_sales("data/salesdaily.csv")

    print("\nRunning forecasts for all drugs...")
    results = run_all_forecasts(long_df)

    print(f"\n{'=' * 50}")
    print(f"Forecast summary ({len(results)} drugs):")
    for r in results:
        flag = "ALERT" if r["predicted_stockout_date"] else "OK"
        print(
            f"  [{flag}] {r.get('drug_name', '?'):15s} | "
            f"stock: {r['current_stock']:>6} | "
            f"stockout: {r['predicted_stockout_date'] or 'none in window'}"
        )

    write_forecasts_to_supabase(results)