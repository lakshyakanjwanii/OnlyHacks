"""
Supabase client wiring.

Two clients are exposed:
- `supabase_anon`  → uses the anon key, respects RLS. Use for anything
                     that should be scoped to the calling user's JWT.
- `supabase_admin` → uses the service_role key, BYPASSES RLS. Use only
                     inside trusted server-side logic (seeding, the
                     ledger service, admin key issuance) — never expose
                     this client's results directly to an unauthenticated
                     caller without your own authorization check first.
"""
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

supabase_anon: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def client_for_request(jwt: str | None) -> Client:
    """
    Returns a Supabase client that carries the caller's JWT, so RLS
    policies apply correctly. Falls back to the anon client (no auth)
    if no JWT was provided.
    """
    if not jwt:
        return supabase_anon
    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    client.postgrest.auth(jwt)
    return client
