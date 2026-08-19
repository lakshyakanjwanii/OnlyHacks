import os
import random
from datetime import timedelta
import numpy as np
import pandas as pd

# Set seeds for reproducibility
np.random.seed(42)
random.seed(42)

# ============================================================
# 1. LOAD & RESHAPE PHARMA SALES DATA
# ============================================================

INPUT_FILE = "salesdaily.csv"
OUTPUT_FOLDER = "synthetic_data"
DATE_COL = "datum"

DRUG_COLS = [
    "M01AB",
    "M01AE",
    "N02BA",
    "N02BE",
    "N05B",
    "N05C",
    "R03",
    "R06",
]

df = pd.read_csv(INPUT_FILE)
df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors="coerce")

# Convert wide to long format
df_long = df.melt(
    id_vars=[DATE_COL],
    value_vars=DRUG_COLS,
    var_name="drug_code",
    value_name="quantity",
).dropna(subset=[DATE_COL, "drug_code", "quantity"])

df_long["quantity"] = pd.to_numeric(df_long["quantity"], errors="coerce")
df_long = df_long.dropna(subset=["quantity"])

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ============================================================
# 2. GENERATE ENTITY & MASTER TABLES
# ============================================================

# 1. Drug Master
drug_categories = {
    "M01AB": ("Anti-inflammatory (Acetic acid)", 15.50),
    "M01AE": ("Anti-inflammatory (Propionic acid)", 12.00),
    "N02BA": ("Analgesics (Salicylic acid)", 8.25),
    "N02BE": ("Analgesics (Pyrazolones/Anilides)", 9.50),
    "N05B": ("Anxiolytics", 25.00),
    "N05C": ("Hypnotics and sedatives", 30.00),
    "R03": ("Drugs for obstructive airway diseases", 45.00),
    "R06": ("Antihistamines for systemic use", 11.75),
}

drug_master_df = pd.DataFrame(
    [
        {
            "drug_code": code,
            "description": info[0],
            "unit_price_usd": info[1],
            "storage_temp_c": random.choice(["2-8°C", "15-25°C", "Room Temp"]),
        }
        for code, info in drug_categories.items()
    ]
)

# 2. Hospitals
NUM_HOSPITALS = 20
hospitals_df = pd.DataFrame(
    {
        "hospital_id": [f"HOSP_{i:03d}" for i in range(1, NUM_HOSPITALS + 1)],
        "hospital_name": [f"General Hospital {i}" for i in range(1, NUM_HOSPITALS + 1)],
        "region": [random.choice(["North", "South", "East", "West", "Central"]) for _ in range(NUM_HOSPITALS)],
        "bed_capacity": np.random.randint(100, 1000, size=NUM_HOSPITALS),
    }
)

# 3. Vendors
NUM_VENDORS = 10
vendors_df = pd.DataFrame(
    {
        "vendor_id": [f"VEND_{i:03d}" for i in range(1, NUM_VENDORS + 1)],
        "vendor_name": [f"Pharma Supply Co {i}" for i in range(1, NUM_VENDORS + 1)],
        "lead_time_days": np.random.randint(2, 14, size=NUM_VENDORS),
        "reliability_score": np.round(np.random.uniform(0.85, 0.99, size=NUM_VENDORS), 2),
    }
)

# 4. Batches
BATCHES_PER_DRUG = 3
batch_records = []
batch_counter = 1

min_date = df_long[DATE_COL].min()

for code in DRUG_COLS:
    for _ in range(BATCHES_PER_DRUG):
        mfg_date = min_date - timedelta(days=random.randint(30, 180))
        exp_date = mfg_date + timedelta(days=random.randint(365, 730))
        batch_records.append(
            {
                "batch_id": f"BAT_{batch_counter:04d}",
                "drug_code": code,
                "vendor_id": random.choice(vendors_df["vendor_id"].tolist()),
                "manufacture_date": mfg_date.strftime("%Y-%m-%d"),
                "expiry_date": exp_date.strftime("%Y-%m-%d"),
                "initial_quantity": random.randint(5000, 20000),
            }
        )
        batch_counter += 1

batches_df = pd.DataFrame(batch_records)

# ============================================================
# 3. GENERATE TRANSACTION & INVENTORY TABLES
# ============================================================

# 5. Hospital Daily Consumption (Distributing daily totals across hospitals)
consumption_records = []
for _, row in df_long.iterrows():
    if row["quantity"] > 0:
        # Sample a subset of hospitals consuming this drug on this date
        active_hospitals = random.sample(
            hospitals_df["hospital_id"].tolist(), k=random.randint(1, min(5, NUM_HOSPITALS))
        )
        split_weights = np.random.dirichlet(np.ones(len(active_hospitals)))
        
        for hosp_id, weight in zip(active_hospitals, split_weights):
            consumed_qty = round(row["quantity"] * weight, 2)
            if consumed_qty > 0:
                consumption_records.append(
                    {
                        "date": row[DATE_COL].strftime("%Y-%m-%d"),
                        "hospital_id": hosp_id,
                        "drug_code": row["drug_code"],
                        "units_consumed": consumed_qty,
                    }
                )

hospital_consumption_df = pd.DataFrame(consumption_records)

# 6. Current Inventory Snapshot
inventory_records = []
for hosp_id in hospitals_df["hospital_id"]:
    for _, batch in batches_df.iterrows():
        if random.random() > 0.3:  # 70% chance a hospital holds this batch
            inventory_records.append(
                {
                    "hospital_id": hosp_id,
                    "drug_code": batch["drug_code"],
                    "batch_id": batch["batch_id"],
                    "current_stock": random.randint(50, 1500),
                    "reorder_level": 200,
                }
            )

inventory_df = pd.DataFrame(inventory_records)

# 7. Shipments
NUM_SHIPMENTS = 150
shipment_records = []
for i in range(1, NUM_SHIPMENTS + 1):
    ship_date = min_date + timedelta(days=random.randint(0, 300))
    shipment_records.append(
        {
            "shipment_id": f"SHIP_{i:05d}",
            "vendor_id": random.choice(vendors_df["vendor_id"].tolist()),
            "hospital_id": random.choice(hospitals_df["hospital_id"].tolist()),
            "batch_id": random.choice(batches_df["batch_id"].tolist()),
            "ship_date": ship_date.strftime("%Y-%m-%d"),
            "quantity_shipped": random.randint(100, 2000),
            "status": random.choice(["Delivered", "In Transit", "Delayed", "Cancelled"]),
        }
    )

shipments_df = pd.DataFrame(shipment_records)

# 8. Inventory With Test Conflicts (Synthetic edge cases for validation/testing)
inventory_conflicts_df = inventory_df.copy()
# Inject negative inventory anomalies
neg_indices = inventory_conflicts_df.sample(n=min(5, len(inventory_conflicts_df))).index
inventory_conflicts_df.loc[neg_indices, "current_stock"] = -50

# Inject non-existent batch anomalies
fake_indices = inventory_conflicts_df.sample(n=min(5, len(inventory_conflicts_df))).index
inventory_conflicts_df.loc[fake_indices, "batch_id"] = "BAT_9999_CORRUPTED"

# ============================================================
# 4. EXPORT ALL TABLES TO CSV
# ============================================================

files_to_export = {
    "drug_master.csv": drug_master_df,
    "hospitals.csv": hospitals_df,
    "vendors.csv": vendors_df,
    "batches.csv": batches_df,
    "inventory.csv": inventory_df,
    "shipments.csv": shipments_df,
    "hospital_consumption.csv": hospital_consumption_df,
    "inventory_with_test_conflicts.csv": inventory_conflicts_df,
}

for filename, dataframe in files_to_export.items():
    path = os.path.join(OUTPUT_FOLDER, filename)
    dataframe.to_csv(path, index=False)
    print(f"Saved: {path} ({len(dataframe)} rows)")

print("\nGeneration complete. Check the synthetic_data folder.")