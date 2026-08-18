import secrets
from fastapi import APIRouter, Depends, HTTPException
from src.middleware.jwt_auth import get_db
from src.middleware.api_key_auth import hash_key
from src.models import ApiKeyCreateIn

router = APIRouter(prefix="/api/v1/keys", tags=["api_keys"])


@router.post("", status_code=201)
async def create_api_key(payload: ApiKeyCreateIn, db=Depends(get_db)):
    """
    Admin-only (enforced by RLS policy `api_keys_insert`, which
    requires auth_role() = 'state' — a non-state caller's JWT-scoped
    insert will simply fail here).

    Generates a random raw key, stores only its SHA-256 hash, and
    returns the raw key ONE TIME in this response. If the caller loses
    it, they must revoke and generate a new one — we cannot retrieve
    it later.
    """
    raw_key = f"osct_{secrets.token_urlsafe(32)}"  # 'osct' = OnlyHacks Supply Chain Tower
    key_hash = hash_key(raw_key)

    result = (
        db.table("api_keys")
        .insert(
            {
                "key_hash": key_hash,
                "owner_id": payload.owner_id,
                "scopes": payload.scopes,
            }
        )
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to create API keys (state role required)",
        )

    return {
        "id": result.data[0]["id"],
        "raw_key": raw_key,
        "scopes": payload.scopes,
    }


@router.patch("/{key_id}/revoke")
async def revoke_api_key(key_id: str, db=Depends(get_db)):
    result = db.table("api_keys").update({"revoked": True}).eq("id", key_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="API key not found")
    return {"revoked": True, "id": key_id}
