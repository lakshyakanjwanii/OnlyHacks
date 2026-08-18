"""
JWT auth for dashboard users (frontend calls). Expects
`Authorization: Bearer <supabase jwt>`.

We don't re-verify the JWT signature ourselves here — we hand it to
Supabase's client, which validates it against the project on every
request and applies RLS accordingly. If it's invalid, Supabase's
query will simply fail/return nothing per RLS rather than raising
here; routes that need a hard 401 for a missing header do that check
directly.
"""
from fastapi import Header
from src.db.supabase_client import client_for_request


async def get_db(authorization: str | None = Header(default=None)):
    """
    FastAPI dependency. Extracts the bearer token (if present) and
    returns a Supabase client scoped to that user's JWT, so RLS
    policies apply. Route handlers should use this client for all
    reads/writes that must respect row-level security.
    """
    jwt = None
    if authorization and authorization.lower().startswith("bearer "):
        jwt = authorization.split(" ", 1)[1]
    return client_for_request(jwt)
