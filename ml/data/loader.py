"""
loader.py — Kaggle Pharma Sales Data ingestion
Dataset: milanzdravkovic/pharma-sales-data
File used: salesdaily.csv  (use this ONLY — others are just aggregations of the same data)

Columns in salesdaily.csv:
  datum       - date string (YYYY-MM-DD or similar)
  M01AB, M01AE, N02BA, N02BE, N05B, N05C, R03, R06  - daily sales per ATC drug category

Output: per-drug daily consumption DataFrame ready for Prophet.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional

# Map ATC codes → human-readable drug names (matches our drugs table seed)
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

# Mock drug IDs to simulate the drugs table until backend is available
MOCK_DRUG_IDS = {atc: f"drug_{i+1:03d}" for i, atc in enumerate(ATC_TO_DRUG_NAME)}


def load_daily_sales(filepath: str = "data/salesdaily_cleaned.csv") -> pd.DataFrame:
    """
    Load and clean salesdaily.csv.
    Returns a tidy long-format DataFrame:
        drug_id | drug_name | atc_code | ds (date) | y (daily_consumption)
    """
    path = Path(filepath)
    if not path.exists():
        home = Path.home()
        candidates = [
            home / "Downloads" / "pharma_sales_sih" / "salesdaily_cleaned.csv",
            home / "Downloads" / "pharma_sales_sih" / "salesdaily_cleaned.csv",
            home / "Downloads" / "pharma_sales_sih" / "salesdaily_long_cleaned.csv",
            home / "Downloads" / "pharma_sales_sih" / "salesdaily_long_cleaned.csv",
            home / "Downloads" / "salesdaily_cleaned.csv",
            Path(__file__).resolve().parent / "salesdaily_cleaned.csv",
            #Path(__file__).resolve().parent / "salesdaily.csv",
            Path("ml/data/salesdaily_cleaned.csv"),
            #Path("ml/data/salesdaily.csv"),
            #Path("data/salesdaily.csv"),
        ]
        for candidate in candidates:
            if candidate.exists():
                path = candidate
                break

    if not path.exists():
        raise FileNotFoundError(f"Dataset not found at '{filepath}' or in Downloads folder.")

    print(f"Loading data from: {path}")
    '''if not path.exists():
        raise FileNotFoundError(
            f"Dataset not found at {filepath}.\n"
            "Download from: https://www.kaggle.com/datasets/milanzdravkovic/pharma-sales-data\n"
            "Place salesdaily.csv in ml/data/"
        )'''

    df = pd.read_csv(path)

    # --- Date column normalisation ---
    # The dataset uses 'datum' as the date column
    date_col = _detect_date_column(df)
    df = df.rename(columns={date_col: "ds"})
    df["ds"] = pd.to_datetime(df["ds"], dayfirst=False)
    df = df.sort_values("ds").reset_index(drop=True)

    # Drop any non-ATC columns we don't need
    atc_cols = [c for c in df.columns if c in ATC_TO_DRUG_NAME]
    if not atc_cols:
        raise ValueError(
            f"No ATC drug columns found. Expected one of {list(ATC_TO_DRUG_NAME.keys())}.\n"
            f"Found columns: {df.columns.tolist()}"
        )

    df = df[["ds"] + atc_cols].copy()

    # --- Clean numeric values ---
    for col in atc_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Fill small gaps (≤3 days) with linear interpolation; longer gaps with column median
    df[atc_cols] = df[atc_cols].interpolate(method="linear", limit=3)
    df[atc_cols] = df[atc_cols].fillna(df[atc_cols].median())

    # Clip negatives (data entry errors)
    df[atc_cols] = df[atc_cols].clip(lower=0)

    # --- Pivot to long format ---
    long_df = df.melt(id_vars=["ds"], value_vars=atc_cols, var_name="atc_code", value_name="y")
    long_df["drug_name"] = long_df["atc_code"].map(ATC_TO_DRUG_NAME)
    long_df["drug_id"] = long_df["atc_code"].map(MOCK_DRUG_IDS)
    long_df = long_df[["drug_id", "drug_name", "atc_code", "ds", "y"]]
    long_df = long_df.sort_values(["drug_id", "ds"]).reset_index(drop=True)

    print(f"✅ Loaded {len(df)} days × {len(atc_cols)} drugs")
    print(f"   Date range: {df['ds'].min().date()} → {df['ds'].max().date()}")
    print(f"   Drugs: {atc_cols}")

    return long_df


def get_drug_series(long_df: pd.DataFrame, drug_id: str) -> pd.DataFrame:
    """
    Extract Prophet-ready time series for a single drug.
    Returns DataFrame with columns: ds, y
    """
    series = long_df[long_df["drug_id"] == drug_id][["ds", "y"]].copy()
    if series.empty:
        raise ValueError(f"No data for drug_id='{drug_id}'. Available: {long_df['drug_id'].unique().tolist()}")
    return series.reset_index(drop=True)


def get_all_drug_ids(long_df: pd.DataFrame) -> list:
    return sorted(long_df["drug_id"].unique().tolist())


def get_drug_info(drug_id: str) -> dict:
    """Return metadata for a drug_id (from mock lookup; replace with DB call later)."""
    for atc, did in MOCK_DRUG_IDS.items():
        if did == drug_id:
            return {
                "drug_id": drug_id,
                "atc_code": atc,
                "drug_name": ATC_TO_DRUG_NAME[atc],
            }
    return {}


# ── internal helpers ──────────────────────────────────────────────────────────

def _detect_date_column(df: pd.DataFrame) -> str:
    """Find the date column regardless of exact name."""
    candidates = [c for c in df.columns if c.lower() in ("datum", "date", "ds", "day")]
    if candidates:
        return candidates[0]
    # fallback: first column that looks like dates
    for col in df.columns:
        try:
            pd.to_datetime(df[col].head(5))
            return col
        except Exception:
            continue
    raise ValueError(f"Cannot find date column in {df.columns.tolist()}")


# ── quick test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    df = load_daily_sales("data/salesdaily.csv")
    print(df.head(10))
    print(f"\nDrug IDs: {get_all_drug_ids(df)}")
    series = get_drug_series(df, "drug_001")
    print(f"\nParacetamol series sample:\n{series.tail()}")