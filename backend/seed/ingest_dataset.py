import os
import uuid
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client

# 1. Resolve paths relative to this script location
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
ENV_PATH = os.path.join(BACKEND_DIR, ".env")

# Fallback: check backend/.env first, then root .env
if os.path.exists(ENV_PATH):
    load_dotenv(ENV_PATH)
else:
    load_dotenv(os.path.join(BACKEND_DIR, "..", ".env"))

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise ValueError(f"Missing SUPABASE_URL or SUPABASE_SERVICE_KEY. Looked in: {ENV_PATH}")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# Resolve data directory (handles either seed/pharma_data or backend/pharma_data)
DATA_DIR = os.path.join(SCRIPT_DIR, "pharma_data", "synthetic_data")
if not os.path.exists(DATA_DIR):
    DATA_DIR = os.path.join(BACKEND_DIR, "pharma_data", "synthetic_data")

def make_uuid(string_seed: str) -> str:
    """Generate a deterministic UUID based on a string for idempotent upserts."""
    return str(uuid.uuid5(uuid.NAMESPACE_OID, str(string_seed)))

def chunked_upsert(table_name: str, records: list, on_conflict: str = "id", chunk_size: int = 200):
    """Upsert data in chunks to prevent PostgREST payload limits."""
    total = len(records)
    for i in range(0, total, chunk_size):
        chunk = records[i:i + chunk_size]
        supabase.table(table_name).upsert(chunk, on_conflict=on_conflict).execute()
    print(f"  -> Upserted {total} records into '{table_name}'.")

def ingest_nodes():
    print("Ingesting nodes (hospitals and vendors)...")
    hospitals_path = os.path.join(DATA_DIR, "hospitals.csv")
    vendors_path = os.path.join(DATA_DIR, "vendors.csv")
    
    nodes_data = []
    
    if os.path.exists(hospitals_path):
        hospitals = pd.read_csv(hospitals_path)
        for _, row in hospitals.iterrows():
            nodes_data.append({
                "id": make_uuid(row["hospital_id"]),
                "node_type": "hospital",
                "node_id": str(row["hospital_id"]),
                "org_id": make_uuid(str(row["hospital_id"]) + "_org"),
                "label": f"{row['hospital_name']} ({row.get('region', 'India')})"
            })
        
    if os.path.exists(vendors_path):
        vendors = pd.read_csv(vendors_path)
        for _, row in vendors.iterrows():
            nodes_data.append({
                "id": make_uuid(row["vendor_id"]),
                "node_type": "vendor",
                "node_id": str(row["vendor_id"]),
                "org_id": make_uuid(str(row["vendor_id"]) + "_org"),
                "label": str(row["vendor_name"])
            })
        
    if nodes_data:
        chunked_upsert("nodes", nodes_data, on_conflict="node_id")

def ingest_drugs():
    print("Ingesting drugs...")
    drugs_path = os.path.join(DATA_DIR, "drug_master.csv")
    if not os.path.exists(drugs_path):
        print(f"Skipping drugs: {drugs_path} not found.")
        return

    drugs = pd.read_csv(drugs_path)
    drugs_data = []
    
    for _, row in drugs.iterrows():
        drugs_data.append({
            "id": make_uuid(row["drug_code"]),
            "name": str(row["description"]),
            "manufacturer": "Kaggle Pharma Synthetic",
            "gtin": f"GTIN-{row['drug_code']}"
        })
        
    if drugs_data:
        chunked_upsert("drugs", drugs_data, on_conflict="gtin")

def ingest_batches():
    print("Ingesting batches (including test conflicts)...")
    batches_path = os.path.join(DATA_DIR, "batches.csv")
    conflicts_path = os.path.join(DATA_DIR, "inventory_with_test_conflicts.csv")
    
    if not os.path.exists(batches_path):
        print(f"Skipping batches: {batches_path} not found.")
        return

    batches = pd.read_csv(batches_path)
    batches_data = []
    processed_batches = set()
    
    for _, row in batches.iterrows():
        batch_id = str(row["batch_id"])
        processed_batches.add(batch_id)
        batches_data.append({
            "id": make_uuid(batch_id),
            "drug_id": make_uuid(row["drug_code"]),
            "batch_number": batch_id,
            "manufacture_date": str(row["manufacture_date"]),
            "expiry_date": str(row["expiry_date"]),
            "created_at": f"{row['manufacture_date']}T00:00:00Z"
        })
        
    # Deliberate conflict injection for the anomaly engine
    if os.path.exists(conflicts_path):
        conflicts = pd.read_csv(conflicts_path)
        for _, row in conflicts.iterrows():
            batch_id = str(row["batch_id"])
            if batch_id in processed_batches:
                batches_data.append({
                    "id": make_uuid(batch_id + "_conflict"),
                    "drug_id": make_uuid(row["drug_code"]),
                    "batch_number": batch_id,
                    "manufacture_date": "2024-01-01",
                    "expiry_date": "2025-12-31",
                })
            
    if batches_data:
        chunked_upsert("batches", batches_data, on_conflict="id")

def ingest_shipments_as_scans():
    print("Ingesting shipments as scan events...")
    shipments_path = os.path.join(DATA_DIR, "shipments.csv")
    if not os.path.exists(shipments_path):
        print(f"Skipping shipments: {shipments_path} not found.")
        return

    shipments = pd.read_csv(shipments_path)
    scan_data = []
    
    for _, row in shipments.iterrows():
        # Dispatch scan
        scan_data.append({
            "id": make_uuid(str(row["shipment_id"]) + "_dispatch"),
            "batch_id": make_uuid(str(row["batch_id"])),
            "node_type": "vendor",
            "node_id": str(row["vendor_id"]),
            "scanned_by": "SYSTEM_INGEST",
            "location": f"Vendor Facility: {row['vendor_id']}",
            "timestamp": f"{row['ship_date']}T08:00:00Z",
            "raw_payload": {
                "shipment_id": row["shipment_id"],
                "status": "dispatch",
                "quantity": int(row["quantity_shipped"])
            }
        })
        
        # Receipt scan
        if row.get("status") == "Delivered":
            scan_data.append({
                "id": make_uuid(str(row["shipment_id"]) + "_receipt"),
                "batch_id": make_uuid(str(row["batch_id"])),
                "node_type": "hospital",
                "node_id": str(row["hospital_id"]),
                "scanned_by": "SYSTEM_INGEST",
                "location": f"Hospital Receiving: {row['hospital_id']}",
                "timestamp": f"{row['ship_date']}T16:00:00Z",
                "raw_payload": {
                    "shipment_id": row["shipment_id"],
                    "status": "received",
                    "quantity": int(row["quantity_shipped"])
                }
            })
            
    if scan_data:
        chunked_upsert("scan_events", scan_data, on_conflict="id")

if __name__ == "__main__":
    print("Starting massive dataset ingestion...")
    ingest_nodes()
    ingest_drugs()
    ingest_batches()
    ingest_shipments_as_scans()
    print("✅ Ingestion complete.")