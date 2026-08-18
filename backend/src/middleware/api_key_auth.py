"""
API key auth for external/vendor integrations (e.g. a vendor's own
system pushing shipment updates into our /scan_events or
/purchase_orders endpoints without a Supabase user session).

Usage: a caller sends header `X-API-Key: <raw key>`.
We hash it and look it up in api_keys. If valid + not revoked + scope
matches, the request proceeds; otherwise 401/403.

Raw keys are NEVER stored — only their SHA-256 hash. The raw key is
shown to the admin exactly once at creation time (see routes/keys.py).
"""
import hashlib
from fastapi import Header, HTTPException, status
from src.db.supabase_client import supabase_admin


def hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


async def require_api_key(x_api_key: str | None = Header(default=None)):
    """
    FastAPI dependency. Attach to any route that external/vendor
    systems (not logged-in dashboard users) should be able to call.
    Returns the api_keys row (with scopes) so the route can check them.
    """
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")

    key_hash = hash_key(x_api_key)
    result = (
        supabase_admin.table("api_keys")
        .select("*")
        .eq("key_hash", key_hash)
        .eq("revoked", False)
        .limit(1)
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key")

    return result.data[0]  # includes owner_id, scopes


def require_scope(key_row: dict, scope: str):
    """Call inside a route after require_api_key to enforce a specific scope."""
    if scope not in key_row.get("scopes", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"API key missing required scope: {scope}",
        )
