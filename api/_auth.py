"""Authorization header → Supabase user 검증 (requests 직접 호출)"""
import os, requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://yattlqdsnrqeqzvcuvuu.supabase.co")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlhdHRscWRzbnJxZXF6dmN1dnV1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzU0Mzc4NDMsImV4cCI6MjA5MTAxMzg0M30.OXYzBYsMHg3ryW7DDr5xljXrgCkL92EIQS2LunAabag")


class _User:
    """Supabase /auth/v1/user JSON을 객체로 래핑 (user.id 등 dot-access)"""
    def __init__(self, data: dict):
        self.id = data.get("id", "")
        self.email = data.get("email", "")
        self.role = data.get("role", "authenticated")
        for k, v in data.items():
            setattr(self, k, v)


def get_user(headers: dict):
    """
    Authorization: Bearer <jwt> 헤더로 Supabase 사용자 검증.
    성공 시 _User 객체 반환, 실패 시 None.
    supabase-py 대신 requests 직접 호출로 라이브러리 버그 우회.
    """
    auth = headers.get("authorization") or headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    token = auth[7:].strip()
    if not token:
        return None
    try:
        resp = requests.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={
                "apikey": SUPABASE_ANON_KEY,
                "Authorization": f"Bearer {token}",
            },
            timeout=8,
        )
        if resp.status_code != 200:
            return None
        return _User(resp.json())
    except Exception:
        return None


def get_user_with_profile(headers: dict):
    """사용자 + profiles 테이블 데이터 반환."""
    from api._db import get_db
    user = get_user(headers)
    if not user:
        return None, None
    db = get_db()
    profile = db.table("profiles").select("*").eq("id", user.id).single().execute()
    return user, profile.data


def require_admin(headers: dict):
    """admin 역할 확인. 아니면 None."""
    user, profile = get_user_with_profile(headers)
    if profile and profile.get("role") == "admin":
        return user, profile
    return None, None
