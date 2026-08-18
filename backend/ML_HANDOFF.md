# ML Pipeline Handoff Guide

## 1. Reading the Dataset
You will find the raw training dataset located at:
`backend/seed/pharma_data/synthetic_data/salesdaily_cleaned.csv`

Use `pandas` to read this CSV and feed it directly into your Prophet forecasting pipeline.

## 2. Pushing Predictions to the Backend (Supabase)
Once you have generated the future forecasts (e.g., next 30 days) for each drug, you must push them to the `forecasts` table in Supabase.

### Schema Requirements for `forecasts` table
- `drug_id` (UUID format, e.g. "22222222-2222-2222-2222-222222222222")
- `date` (String, "YYYY-MM-DD")
- `predicted_stock` (Float/Numeric)
- `predicted_stockout_date` (String, "YYYY-MM-DD", optional/nullable)
- `reorder_threshold` (Float/Numeric, optional/nullable)

### 3. Copy-Pasteable Database Insertion Snippet
Use this snippet in your ML pipeline script to authenticate and batch-insert your predictions safely.

```python
import os
import pandas as pd
from supabase import create_client, Client

# 1. Initialize the Supabase Client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise ValueError("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY environment variables")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# 2. Prepare your forecast data
# Replace this with your actual Prophet output mapped to the schema
predictions = [
    {
        "drug_id": "22222222-2222-2222-2222-222222222222", 
        "date": "2025-04-11",
        "predicted_stock": 307.4,
        "predicted_stockout_date": "2025-04-13",
        "reorder_threshold": 2779.0
    },
    {
        "drug_id": "22222222-2222-2222-2222-222222222222", 
        "date": "2025-04-12",
        "predicted_stock": 111.9,
        "predicted_stockout_date": "2025-04-13",
        "reorder_threshold": 2779.0
    }
]

# 3. Batch Upsert to Supabase
# We use upsert to ensure that if the pipeline re-runs, it updates existing records instead of duplicating.
try:
    response = supabase.table("forecasts").upsert(predictions).execute()
    print(f"✅ Successfully upserted {len(response.data)} forecast records.")
except Exception as e:
    print(f"❌ Failed to push forecasts to Supabase: {e}")
```
