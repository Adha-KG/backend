# app/auth/supabase_client.py
import os

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

# Supabase configuration
url: str = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
anon_key: str = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
service_role_key: str = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

# Validate environment variables
if not url:
    raise ValueError(
        "SUPABASE_URL environment variable is not set. "
        "Please check your .env file and ensure SUPABASE_URL is configured."
    )
if not anon_key:
    raise ValueError(
        "SUPABASE_KEY or SUPABASE_ANON_KEY environment variable is not set. "
        "Please check your .env file and ensure one of these keys is configured."
    )

# Create client with anon key for auth operations
# This allows Supabase Auth to work properly with RLS policies
supabase: Client = create_client(url, anon_key)

# Optional: Create service role client for admin operations (bypasses RLS)
# Only use this for admin operations that require elevated privileges
service_client: Client | None = None
if service_role_key:
    service_client = create_client(url, service_role_key)

def get_supabase() -> Client:
    """Get Supabase client with anon key (for regular auth operations)"""
    return supabase

def get_service_client() -> Client:
    """Get Supabase client with service role key (for admin operations)"""
    if service_client is None:
        raise ValueError(
            "Service role client not configured. "
            "Set SUPABASE_SERVICE_KEY or SUPABASE_SERVICE_ROLE_KEY in your .env file."
        )
    return service_client
