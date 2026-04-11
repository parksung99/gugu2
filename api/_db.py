"""공용 Supabase 클라이언트 (service role — RLS 우회)"""
import os, json
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://yattlqdsnrqeqzvcuvuu.supabase.co")
SUPABASE_SERVICE_KEY = (
    os.environ.get("SUPABASE_SERVICE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or ""
)

_client: Client | None = None

def get_db() -> Client:
    global _client
    if _client is None:
        if not SUPABASE_SERVICE_KEY:
            raise RuntimeError("Missing SUPABASE_SERVICE_KEY or SUPABASE_KEY environment variable")
        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _client


def ok(data, status=200):
    return json.dumps({"ok": True, "data": data}), status, _cors_headers()

def err(message, status=400):
    return json.dumps({"ok": False, "error": message}), status, _cors_headers()

def _cors_headers():
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
    }
