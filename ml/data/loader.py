"""
loader.py -- Kaggle Pharma Sales Data ingestion
Dataset: milanzdravkovic/pharma-sales-data
File used: salesdaily.csv  (use this ONLY -- others are just aggregations of the same data)

Columns in salesdaily.csv:
  datum       - date string (YYYY-MM-DD or similar)
  M01AB, M01AE, N02BA, N02BE, N05B, N05C, R03, R06  - daily sales per ATC drug category

Output: per-drug daily consumption DataFrame ready for Prophet.
"""

import os
import sys
import uuid
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np
from dotenv import load_dotenv
from supabase import create_client, Client

# Load env variables from backend/.env (where real credentials live)
load_dotenv(str(Path(__file__).resolve().parent.parent.parent / "backend" / ".env"))

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", os.getenv("SUPABASE_KEY"))

# ---- ATC code mappings -------------------------------------------------------

# Map ATC codes to human-readable drug names (matches our drugs table seed)
ATC_TO_DRUG_NAME = {
    "M01AB": "Diclofenac",         # Anti-inflammatory, acetic acid derivatives
    "M01AE": "Ibuprofen",          # Anti-inflammatory, propionic acid derivatives
    "N02BA": "Aspirin",            # Analgesic, salicylic acid
    "N02BE": "Paracetamol",        # Analgesic, anilides (Paracetamol/Acetaminophen)
    "N05B":  "Diazepam",           # Anxiolytic (benzodiazepines)
    "N05C":  "Nitrazepam",         # Hypnotic/sedative
    "R03":   "Salbutamol",         # Bronchodilator
    "R06":   "Loratadine",         # Antihistamine
}

# Reverse map for lookup by drug name
DRUG_NAME_TO_ATC = {v: k for k, v in ATC_TO_DRUG_NAME.items()}

# ---- Drug ID mapping ---------------------------------------------------------
# Stable fallback IDs used when Supabase is not reachable.
# Generated with uuid5(NAMESPACE_DNS, atc_code) for reproducibility.
#
# Two overrides align with the hardcoded UUIDs in backend/seed/seed.sql:
#   N02BE (Paracetamol) -> 11111111-... matches the CAG conflict demo drug
#   M01AE (Ibuprofen slot used as Amoxicillin proxy) -> 22222222-...

MOCK_DRUG_IDS: dict = {
    atc: str(uuid.uuid5(uuid.NAMESPACE_DNS, atc))
    for atc in ATC_TO_DRUG_NAME.keys()
}
MOCK_DRUG_IDS["N02BE"] = "11111111-1111-1111-1111-111111111111"
MOCK_DRUG_IDS["M01AE"] = "22222222-2222-2222-2222-222222222222"

# Reverse map: drug_id -> {atc_code, drug_name} for O(1) lookups in get_drug_info()
DRUG_ID_MAP: dict = {
    did: {"atc_code": atc, "drug_name": ATC_TO_DRUG_NAME[atc]}
    for atc, did in MOCK_DRUG_IDS.items()
}

# ---- Optional live Supabase drug-ID lookup -----------------------------------

_real_drug_ids: Optional[dict] = None


def get_real_drug_ids() -> dict:
    """
    Fetch real drug UUIDs from Supabase drugs table, keyed by ATC code.
    Returns an empty dict (and logs a warning) if Supabase is unreachable.
    Cached after first successful call.
    """
    global _real_drug_ids
    if _real_drug_ids is not None:
        return _real_drug_ids

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("   SUPABASE_URL or SUPABASE_KEY missing -- using MOCK_DRUG_IDS fallback.")
        return {}

    try:
        client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        response = client.table("drugs").select("id, gtin").execute()

        mapping: dict = {}
        for row in (response.data or []):
            gtin = row.get("gtin", "")
            if gtin.startswith("GTIN-"):
                atc_code = gtin.replace("GTIN-", "")
                if atc_code in ATC_TO_DRUG_NAME:
                    mapping[atc_code] = row["id"]
        _real_drug_ids = mapping
        # Update DRUG_ID_MAP so get_drug_info() works for live UUIDs
        for atc_code, drug_uuid in mapping.items():
            DRUG_ID_MAP[drug_uuid] = {
                "atc_code": atc_code,
                "drug_name": ATC_TO_DRUG_NAME[atc_code],
            }
        print(f"Loaded {len(mapping)} drug IDs from Supabase.")
        return mapping
    except Exception as exc:
        print(f"   Error fetching drug IDs from Supabase: {exc}")
        return {}


# ---- Data loading ------------------------------------------------------------

def load_daily_sales(filepath: str = "data/salesdaily.csv") -> pd.DataFrame:
    """
    Load and clean salesdaily.csv.
    Returns a tidy long-format DataFrame:
        drug_id | drug_name | atc_code | ds (date) | y (daily_consumption)

    drug_id is populated from Supabase if reachable, otherwise falls back to
    the stable MOCK_DRUG_IDS dict so the service starts without a DB connection.
    """
    # Prefer a path relative to this file
    base_dir = Path(__file__).resolve().parent
    candidates = [
        Path(filepath),
        base_dir / "salesdaily_cleaned.csv",
        base_dir / "salesdaily.csv",
        base_dir.parent / "data" / "salesdaily_cleaned.csv",
        base_dir.parent / "data" / "salesdaily.csv",
        Path.cwd() / "ml" / "data" / "salesdaily_cleaned.csv",
    ]

    path = None
    for candidate in candidates:
        if candidate.exists():
            path = candidate
            break

    if not path:
        raise FileNotFoundError(
            f"Dataset not found at any candidate path. E.g. {candidates[1]}"
        )

    print(f"Loading data from: {path}")

    df = pd.read_csv(path)

    # Date column normalisation
    date_col = _detect_date_column(df)
    df = df.rename(columns={date_col: "ds"})
    df["ds"] = pd.to_datetime(df["ds"], dayfirst=False)
    df = df.sort_values("ds").reset_index(drop=True)

    # Keep only recognised ATC columns
    atc_cols = [c for c in df.columns if c in ATC_TO_DRUG_NAME]
    if not atc_cols:
        raise ValueError(
            f"No ATC drug columns found. Expected one of {list(ATC_TO_DRUG_NAME.keys())}.\n"
            f"Found columns: {df.columns.tolist()}"
        )

    df = df[["ds"] + atc_cols].copy()

    # Clean numeric values
    for col in atc_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Fill small gaps (<=3 days) with linear interpolation; longer gaps with median
    df[atc_cols] = df[atc_cols].interpolate(method="linear", limit=3)
    df[atc_cols] = df[atc_cols].fillna(df[atc_cols].median())

    # Clip negatives (data entry errors)
    df[atc_cols] = df[atc_cols].clip(lower=0)

    # Resolve drug_id mapping: try Supabase live IDs, fall back to MOCK_DRUG_IDS
    live_ids = get_real_drug_ids()
    drug_id_source = {atc: live_ids.get(atc, MOCK_DRUG_IDS[atc]) for atc in atc_cols}

    # Pivot to long format
    long_df = df.melt(id_vars=["ds"], value_vars=atc_cols, var_name="atc_code", value_name="y")
    long_df["drug_name"] = long_df["atc_code"].map(ATC_TO_DRUG_NAME)
    long_df["drug_id"]   = long_df["atc_code"].map(drug_id_source)
    long_df = long_df[["drug_id", "drug_name", "atc_code", "ds", "y"]]
    long_df = long_df.sort_values(["drug_id", "ds"]).reset_index(drop=True)

    print(f"Loaded {len(df)} days x {len(atc_cols)} drugs")
    print(f"   Date range: {df['ds'].min().date()} -> {df['ds'].max().date()}")
    print(f"   Drugs: {atc_cols}")

    return long_df


# ---- Public helpers ----------------------------------------------------------

def get_drug_series(long_df: pd.DataFrame, drug_id: str) -> pd.DataFrame:
    """
    Extract Prophet-ready time series for a single drug.
    Returns DataFrame with columns: ds, y
    """
    series = long_df[long_df["drug_id"] == drug_id][["ds", "y"]].copy()
    if series.empty:
        raise ValueError(
            f"No data for drug_id='{drug_id}'. "
            f"Available: {long_df['drug_id'].unique().tolist()}"
        )
    return series.reset_index(drop=True)


def get_all_drug_ids(long_df: pd.DataFrame) -> list:
    return sorted(long_df["drug_id"].unique().tolist())


def get_drug_info(drug_id: str) -> dict:
    """Return metadata for a drug_id. Looks up DRUG_ID_MAP built from MOCK_DRUG_IDS."""
    info = DRUG_ID_MAP.get(drug_id)
    if info:
        return {
            "drug_id": drug_id,
            "atc_code": info["atc_code"],
            "drug_name": info["drug_name"],
        }
    return {}


# ---- Internal helpers --------------------------------------------------------

def _detect_date_column(df: pd.DataFrame) -> str:
    """Find the date column regardless of exact name."""
    candidates = [c for c in df.columns if c.lower() in ("datum", "date", "ds", "day")]
    if candidates:
        return candidates[0]
    # fallback: first column that parses as dates
    for col in df.columns:
        try:
            pd.to_datetime(df[col].head(5))
            return col
        except Exception:
            continue
    raise ValueError(f"Cannot find date column in {df.columns.tolist()}")


# ---- Quick test --------------------------------------------------------------
if __name__ == "__main__":
    df = load_daily_sales("data/salesdaily.csv")
    print(df.head(10))
    print(f"\nDrug IDs: {get_all_drug_ids(df)}")
    first_id = get_all_drug_ids(df)[0]
    series = get_drug_series(df, first_id)
    print(f"\nSample series for {first_id}:\n{series.tail()}")