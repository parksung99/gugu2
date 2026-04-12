"""
Kakao OAuth bridge.

GET /api/auth/kakao          -> redirect to Kakao OAuth
GET /api/auth/kakao?code=... -> create/link Supabase user, then issue a session
"""
from http.server import BaseHTTPRequestHandler
import os
import traceback
import uuid
from urllib.parse import parse_qs, urlencode, urlparse

import requests as req

from api._db import get_db


KAKAO_CLIENT_ID = os.environ.get("KAKAO_CLIENT_ID", "")
KAKAO_CLIENT_SECRET = os.environ.get("KAKAO_CLIENT_SECRET", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://yattlqdsnrqeqzvcuvuu.supabase.co").rstrip("/")
SUPABASE_SERVICE_KEY = (
    os.environ.get("SUPABASE_SERVICE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or ""
)


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            base_url = self._base_url()
            redirect_uri = f"{base_url}/api/auth/kakao"
            qs = parse_qs(urlparse(self.path).query)
            code = qs.get("code", [None])[0]
            kakao_error = qs.get("error", [None])[0]

            if kakao_error:
                print(f"[kakao] oauth error: {kakao_error}")
                return self._redirect(f"{base_url}/login.html?error=kakao_token")

            if not KAKAO_CLIENT_ID:
                print("[kakao] missing KAKAO_CLIENT_ID")
                return self._redirect(f"{base_url}/login.html?error=server_config")

            if not code:
                params = urlencode(
                    {
                        "client_id": KAKAO_CLIENT_ID,
                        "redirect_uri": redirect_uri,
                        "response_type": "code",
                        "scope": "profile_nickname",
                    }
                )
                return self._redirect(f"https://kauth.kakao.com/oauth/authorize?{params}")

            token_resp = self._request_kakao_token(code, redirect_uri)
            if token_resp.status_code != 200:
                print(f"[kakao] token error: {token_resp.status_code} {token_resp.text}")
                return self._redirect(f"{base_url}/login.html?error=kakao_token")

            kakao_token = token_resp.json().get("access_token")
            if not kakao_token:
                print("[kakao] token response missing access_token")
                return self._redirect(f"{base_url}/login.html?error=kakao_token")

            user_info = self._request_kakao_user(kakao_token)
            if not user_info:
                return self._redirect(f"{base_url}/login.html?error=kakao_user")

            kakao_id = str(user_info["id"])
            kakao_account = user_info.get("kakao_account", {})
            properties = user_info.get("properties", {})
            email = kakao_account.get("email") or f"{kakao_id}@kakao.gugu"
            nickname = properties.get("nickname") or "Kakao user"

            if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
                print("[kakao] missing SUPABASE_URL or SUPABASE_SERVICE_KEY")
                return self._redirect(f"{base_url}/login.html?error=server_config")

            user_id = self._ensure_supabase_user(email, nickname, kakao_id)
            if not user_id:
                return self._redirect(f"{base_url}/login.html?error=kakao_server")

            self._link_profile(user_id, kakao_id, nickname)

            action_link = self._generate_login_link(email, f"{base_url}/index.html")
            if not action_link:
                return self._redirect(f"{base_url}/login.html?error=kakao_session")

            return self._redirect(action_link)

        except Exception as e:
            print(f"[kakao] unhandled error: {e}")
            traceback.print_exc()
            self._redirect(f"{self._base_url()}/login.html?error=kakao_server")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def _base_url(self):
        configured = os.environ.get("APP_BASE_URL") or os.environ.get("PUBLIC_URL")
        if configured:
            return configured.rstrip("/")

        host = self.headers.get("x-forwarded-host") or self.headers.get("host")
        proto = self.headers.get("x-forwarded-proto") or "https"
        if host:
            return f"{proto}://{host}".rstrip("/")

        return "https://gugu2-six.vercel.app"

    def _request_kakao_token(self, code, redirect_uri):
        token_data = {
            "grant_type": "authorization_code",
            "client_id": KAKAO_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "code": code,
        }
        if KAKAO_CLIENT_SECRET:
            token_data["client_secret"] = KAKAO_CLIENT_SECRET

        return req.post("https://kauth.kakao.com/oauth/token", data=token_data, timeout=10)

    def _request_kakao_user(self, kakao_token):
        resp = req.get(
            "https://kapi.kakao.com/v2/user/me",
            headers={"Authorization": f"Bearer {kakao_token}"},
            timeout=10,
        )
        if resp.status_code != 200:
            print(f"[kakao] user error: {resp.status_code} {resp.text}")
            return None

        data = resp.json()
        if "id" not in data:
            print(f"[kakao] user response missing id: {data}")
            return None
        return data

    def _admin_headers(self):
        return {
            "apikey": SUPABASE_SERVICE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            "Content-Type": "application/json",
        }

    def _ensure_supabase_user(self, email, nickname, kakao_id):
        existing_profile_id = self._find_profile_user_id(kakao_id)
        if existing_profile_id:
            return existing_profile_id

        headers = self._admin_headers()
        create_resp = req.post(
            f"{SUPABASE_URL}/auth/v1/admin/users",
            headers=headers,
            json={
                "email": email,
                "password": str(uuid.uuid4()),
                "email_confirm": True,
                "user_metadata": {"name": nickname, "role": "consumer", "provider": "kakao"},
            },
            timeout=10,
        )

        if create_resp.status_code in (200, 201):
            return create_resp.json().get("id")

        print(f"[kakao] create user failed: {create_resp.status_code} {create_resp.text}")
        return self._find_auth_user_id_by_email(email)

    def _find_profile_user_id(self, kakao_id):
        try:
            existing = (
                get_db()
                .table("profiles")
                .select("id")
                .eq("kakao_id", kakao_id)
                .execute()
            )
            if existing.data:
                return existing.data[0].get("id")
        except Exception as e:
            print(f"[kakao] profile lookup failed: {e}")
        return None

    def _find_auth_user_id_by_email(self, email):
        try:
            user_list = req.get(
                f"{SUPABASE_URL}/auth/v1/admin/users",
                headers=self._admin_headers(),
                timeout=10,
            ).json()
            for user in user_list.get("users", []):
                if user.get("email") == email:
                    return user.get("id")
        except Exception as e:
            print(f"[kakao] user lookup failed: {e}")
        return None

    def _link_profile(self, user_id, kakao_id, nickname):
        try:
            get_db().table("profiles").update(
                {"kakao_id": kakao_id, "name": nickname}
            ).eq("id", user_id).execute()
        except Exception as e:
            print(f"[kakao] profile update failed: {e}")

    def _generate_login_link(self, email, redirect_to):
        resp = req.post(
            f"{SUPABASE_URL}/auth/v1/admin/generate_link",
            headers=self._admin_headers(),
            json={"type": "magiclink", "email": email, "redirect_to": redirect_to},
            timeout=10,
        )
        if resp.status_code not in (200, 201):
            print(f"[kakao] generate link failed: {resp.status_code} {resp.text}")
            return None
        return resp.json().get("action_link")

    def _redirect(self, url):
        self.send_response(302)
        self.send_header("Location", url)
        self.end_headers()

    def log_message(self, *_):
        pass
