from fastapi import APIRouter, Depends, HTTPException
from src.middleware.jwt_auth import get_db
from src.models import DrugIn

router = APIRouter(prefix="/api/v1/drugs", tags=["drugs"])


@router.get("")
async def list_drugs(db=Depends(get_db)):
    result = db.table("drugs").select("*").execute()
    return result.data


@router.get("/{drug_id}")
async def get_drug(drug_id: str, db=Depends(get_db)):
    result = db.table("drugs").select("*").eq("id", drug_id).limit(1).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Drug not found")
    return result.data[0]


@router.post("", status_code=201)
async def create_drug(payload: DrugIn, db=Depends(get_db)):
    result = db.table("drugs").insert(payload.model_dump()).execute()
    return result.data[0]
