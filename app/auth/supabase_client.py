
import config
from supabase import Client, create_client

# Module-level client instances
_client: Client | None = None
_admin_client: Client | None = None

def get_client() -> Client:
    """Get Supabase client with anon key for general operations"""
    global _client
    if _client is None:
        _client = create_client(
            config.SUPABASE_URL,
            config.SUPABASE_ANON_KEY
        )
    return _client

def get_admin_client() -> Client:
    """Get Supabase client with service key for admin operations"""
    global _admin_client
    if _admin_client is None:
        _admin_client = create_client(
            config.SUPABASE_URL,
            config.SUPABASE_SERVICE_KEY
        )
    return _admin_client
