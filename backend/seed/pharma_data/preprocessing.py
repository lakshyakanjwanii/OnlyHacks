import pandas as pd
import numpy as np

# 1. Load raw dataset
df = pd.read_csv("salesdaily.csv")

# 2. Fix date formatting
date_col = "datum" if "datum" in df.columns else "date"
df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
df = df.dropna(subset=[date_col]).sort_values(date_col)

# 3. Clean numeric drug columns
DRUG_COLS = ["M01AB", "M01AE", "N02BA", "N02BE", "N05B", "N05C", "R03", "R06"]
present_drugs = [col for col in DRUG_COLS if col in df.columns]

for col in present_drugs:
    # Convert text/corrupted values to numeric NaN, then fill with 0
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    # Clip negative values to zero (sales cannot be negative)
    df[col] = df[col].clip(lower=0.0)
    # Cap extreme anomalies/spikes (above 99th percentile) to prevent model distortion
    upper_threshold = df[col].quantile(0.99) * 1.5
    df[col] = np.where(df[col] > upper_threshold, upper_threshold, df[col])

# 4. Export cleaned wide format (for general statistical use/ML)
df.to_csv("salesdaily_cleaned.csv", index=False)

# 5. Export clean long/tidy format (standard structure for time-series forecasting)
df_long = df.melt(
    id_vars=[date_col],
    value_vars=present_drugs,
    var_name="drug_id",
    value_name="sales_volume"
).rename(columns={date_col: "date"})

df_long.to_csv("salesdaily_long_cleaned.csv", index=False)

print(f"Wide cleaned shape: {df.shape}")
print(f"Long cleaned shape: {df_long.shape}")
print(df_long.head())