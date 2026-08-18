from fastapi import APIRouter, Depends, HTTPException
from src.middleware.jwt_auth import get_db
from src.models import PurchaseOrderIn

router = APIRouter(prefix="/api/v1/purchase_orders", tags=["purchase_orders"])


@router.get("")
async def list_purchase_orders(vendor_id: str | None = None, db=Depends(get_db)):
    query = db.table("purchase_orders").select("*")
    if vendor_id:
        query = query.eq("vendor_id", vendor_id)
    result = query.execute()
    return result.data


@router.post("", status_code=201)
async def create_purchase_order(payload: PurchaseOrderIn, db=Depends(get_db)):
    result = db.table("purchase_orders").insert(payload.model_dump()).execute()
    return result.data[0]


@router.patch("/{po_id}/status")
async def update_status(po_id: str, status: str, db=Depends(get_db)):
    if status not in ("pending", "shipped", "delivered"):
        raise HTTPException(status_code=400, detail="Invalid status")
    result = (
        db.table("purchase_orders").update({"status": status}).eq("id", po_id).execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    return result.data[0]
