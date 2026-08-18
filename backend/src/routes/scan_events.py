from fastapi import APIRouter, Depends, Header
from src.middleware.jwt_auth import get_db
from src.middleware.api_key_auth import require_api_key, require_scope
from src.db.supabase_client import supabase_admin
from src.models import ScanEventIn

router = APIRouter(prefix="/api/v1/scan_events", tags=["scan_events"])


@router.get("")
async def list_scan_events(batch_id: str | None = None, db=Depends(get_db)):
    query = db.table("scan_events").select("*")
    if batch_id:
        query = query.eq("batch_id", batch_id)
    result = query.order("timestamp", desc=True).execute()
    return result.data


@router.post("", status_code=201)
async def create_scan_event(
    payload: ScanEventIn,
    x_api_key: str | None = Header(default=None),
    db=Depends(get_db),
):
    """
    Dual-auth: the scanner PWA (teammate 4) may call this either as a
    logged-in dashboard user (JWT) OR as an offline/background-sync
    client authenticating with an API key. If an API key is present,
    validate it and use the admin client (bypasses RLS, since the
    scanner isn't a Supabase session); otherwise fall back to the
    JWT-scoped client so RLS applies normally.
    """
    data = payload.model_dump(mode="json", exclude_none=True)

    if x_api_key:
        key_row = await require_api_key(x_api_key)
        require_scope(key_row, "scan_events:write")
        result = supabase_admin.table("scan_events").insert(data).execute()
    else:
        result = db.table("scan_events").insert(data).execute()

    # NOTE: the anomaly engine (teammate 3) should be wired to fire on
    # inserts to this table — either via a Postgres trigger calling out,
    # or by teammate 3's service polling/subscribing to Supabase
    # Realtime on `scan_events`. This route just writes the row.
    return result.data[0]
