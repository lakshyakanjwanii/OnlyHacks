from fastapi import APIRouter, Depends
from src.middleware.jwt_auth import get_db

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


@router.get("")
async def list_alerts(recipient: str | None = None, db=Depends(get_db)):
    query = db.table("alerts").select("*")
    if recipient:
        query = query.eq("recipient", recipient)
    result = query.order("created_at", desc=True).execute()
    return result.data
