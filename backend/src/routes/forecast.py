from fastapi import APIRouter, Depends, HTTPException
from src.middleware.jwt_auth import get_db

router = APIRouter(prefix="/api/v1/forecast", tags=["forecast"])


@router.get("/{drug_id}")
async def get_forecast(drug_id: str, db=Depends(get_db)):
    """
    Proxy endpoint. Actual forecasting logic lives in the ML service
    (teammate 5, /ml). This route just reads whatever the ML pipeline
    has already written into the `forecasts` table and reshapes it
    into exactly what the frontend's ForecastChart component expects:

        { drug, dates[], predicted_stock[], reorder_threshold,
          predicted_stockout_date }

    If the ML service is deployed separately and reachable over HTTP,
    swap the block below for an httpx call to it instead of reading
    the cache table directly — the response shape must stay identical
    either way.
    """
    drug_result = db.table("drugs").select("name").eq("id", drug_id).limit(1).execute()
    if not drug_result.data:
        raise HTTPException(status_code=404, detail="Drug not found")
    drug_name = drug_result.data[0]["name"]

    rows = (
        db.table("forecasts")
        .select("*")
        .eq("drug_id", drug_id)
        .order("date")
        .execute()
        .data
    )

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="No forecast available yet for this drug — ML pipeline hasn't run.",
        )

    return {
        "drug": drug_name,
        "dates": [r["date"] for r in rows],
        "predicted_stock": [r["predicted_stock"] for r in rows],
        "reorder_threshold": rows[-1].get("reorder_threshold"),
        "predicted_stockout_date": rows[-1].get("predicted_stockout_date"),
    }
