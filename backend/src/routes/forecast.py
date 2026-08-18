from fastapi import APIRouter, HTTPException
import httpx
import os
import logging

router = APIRouter(tags=["Forecasts"])
logger = logging.getLogger(__name__)

# Fetch the URL from .env, default to localhost if missing
ML_SERVICE_URL = os.getenv("ML_SERVICE_URL", "http://localhost:8001")

@router.get("/api/v1/forecast/{drug_id}")
async def get_live_forecast(drug_id: str):
    """
    Proxies the forecast request to the ML microservice.
    """
    try:
        # httpx handles the async request to Teammate 5's service
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{ML_SERVICE_URL}/forecast/{drug_id}")
            
            # If the ML service returns a 404 or 500, catch it safely
            response.raise_for_status()
            
            # Return the exact JSON straight to the React frontend
            return response.json()
            
    except httpx.HTTPStatusError as e:
        logger.error(f"ML Service returned an error: {e}")
        raise HTTPException(status_code=e.response.status_code, detail="ML Forecasting service returned an error.")
    except httpx.RequestError as e:
        logger.error(f"Could not reach ML Service: {e}")
        raise HTTPException(status_code=503, detail="ML Forecasting service is currently unreachable.")
