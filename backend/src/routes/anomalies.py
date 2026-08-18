from fastapi import APIRouter, Depends, HTTPException
from src.middleware.jwt_auth import get_db

router = APIRouter(prefix="/api/v1/anomalies", tags=["anomalies"])


@router.get("")
async def list_anomalies(resolved: bool | None = None, db=Depends(get_db)):
    query = db.table("anomalies").select("*")
    if resolved is not None:
        query = query.eq("resolved", resolved)
    result = query.order("created_at", desc=True).execute()
    return result.data


@router.patch("/{anomaly_id}/resolve")
async def resolve_anomaly(anomaly_id: str, db=Depends(get_db)):
    """
    Called from the frontend's Anomaly Panel resolve/acknowledge action.
    Rows themselves are written by teammate 3's rule engine, not here.
    """
    result = (
        db.table("anomalies")
        .update({"resolved": True})
        .eq("id", anomaly_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    return result.data[0]
