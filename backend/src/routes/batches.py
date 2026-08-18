from fastapi import APIRouter, Depends, HTTPException
from src.middleware.jwt_auth import get_db
from src.models import BatchIn

router = APIRouter(prefix="/api/v1/batches", tags=["batches"])


@router.get("")
async def list_batches(drug_id: str | None = None, db=Depends(get_db)):
    query = db.table("batches").select("*")
    if drug_id:
        query = query.eq("drug_id", drug_id)
    result = query.execute()
    return result.data


@router.get("/{batch_id}")
async def get_batch(batch_id: str, db=Depends(get_db)):
    result = db.table("batches").select("*").eq("id", batch_id).limit(1).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Batch not found")
    return result.data[0]


@router.post("", status_code=201)
async def create_batch(payload: BatchIn, db=Depends(get_db)):
    """
    NOTE: intentionally does NOT block on a duplicate
    (drug_id, batch_number) with a different expiry_date — that
    conflict is exactly what the anomaly engine (teammate 3) is
    responsible for catching after the write. The ledger service
    should be triggered (via its own hook/subscription on this table)
    immediately after insert.
    """
    data = payload.model_dump(mode="json")
    result = db.table("batches").insert(data).execute()
    return result.data[0]


@router.get("/{batch_id}/audit-trail")
async def get_batch_audit_trail(batch_id: str, db=Depends(get_db)):
    """
    Convenience endpoint for the frontend's Audit Trail view — reads
    ledger_entries filtered to this batch (ref_table='batches').
    """
    result = (
        db.table("ledger_entries")
        .select("*")
        .eq("ref_table", "batches")
        .eq("ref_id", batch_id)
        .order("created_at")
        .execute()
    )
    return result.data
