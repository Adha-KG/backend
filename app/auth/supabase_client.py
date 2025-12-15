# app/auth/supabase_client.py
import os

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

url: str = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_ANON_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")

# Validate environment variables
if not url:
    raise ValueError(
        "SUPABASE_URL environment variable is not set. "
        "Please check your .env file and ensure SUPABASE_URL is configured."
    )
if not key:
    raise ValueError(
        "SUPABASE_KEY or SUPABASE_ANON_KEY environment variable is not set. "
        "Please check your .env file and ensure one of these keys is configured."
    )

supabase: Client = create_client(url, key)

def get_supabase() -> Client:
    return supabase
