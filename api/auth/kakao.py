"""
GET /api/auth/kakao          — 카카오 OAuth 시작 (redirect)
GET /api/auth/kakao?code=... — 카카오 callback → Supabase 세션 생성
환경변수: KAKAO_CLIENT_ID, KAKAO_CLIENT_SECRET, APP_BASE_URL
"""
from http.server import BaseHTTPRequestHandler
import json, os, uuid, traceback
import requests as req
from urllib.parse import urlparse, parse_qs, urlencode
from api._db import get_db

KAKAO_CLIENT_ID     = os.environ.get("KAKAO_CLIENT_ID", "")
KAKAO_CLIENT_SECRET = os.environ.get("KAKAO_CLIENT_SECRET", "")
APP_BASE_URL        = os.environ.get("APP_BASE_URL", "https://gugu2-six.vercel.app")
REDIRECT_URI        = f"{APP_BASE_URL}/api/auth/kakao"


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            qs   = parse_qs(urlparse(self.path).query)
            code = qs.get("code", [None])[0]

            if not code:
                # 1단계: 카카오 로그인 페이지로 리다이렉트
                params = urlencode({
                    "client_id":     KAKAO_CLIENT_ID,
                    "redirect_uri":  REDIRECT_URI,
                    "response_type": "code",
                    "scope":         "profile_nickname",
                })
                self._redirect(f"https://kauth.kakao.com/oauth/authorize?{params}")
                return

            # 2단계: code → access_token
            token_data = {
                "grant_type":    "authorization_code",
                "client_id":     KAKAO_CLIENT_ID,
                "redirect_uri":  REDIRECT_URI,
                "code":          code,
            }
            if KAKAO_CLIENT_SECRET:
                token_data["client_secret"] = KAKAO_CLIENT_SECRET

            token_resp = req.post("https://kauth.kakao.com/oauth/token",
                                  data=token_data, timeout=10)
            if token_resp.status_code != 200:
                print(f"[kakao] token error: {token_resp.status_code} {token_resp.text}")
                return self._redirect(f"{APP_BASE_URL}/login.html?error=kakao_token")

            kakao_token = token_resp.json()["access_token"]

            # 3단계: 사용자 정보
            me = req.get("https://kapi.kakao.com/v2/user/me",
                headers={"Authorization": f"Bearer {kakao_token}"},
                timeout=10).json()

            kakao_id = str(me["id"])
            email    = me.get("kakao_account", {}).get("email") or f"{kakao_id}@kakao.gugu"
            nickname = me.get("properties", {}).get("nickname", "카카오유저")

            db = get_db()

            # 기존 유저 조회 (kakao_id로)
            try:
                existing = db.table("profiles").select("id").eq("kakao_id", kakao_id).execute()
            except Exception:
                existing = type('R', (), {'data': None})()

            if existing.data:
                # 이미 가입된 유저
                self._redirect(f"{APP_BASE_URL}/login.html?kakao_token=done&email={email}")
                return

            # 신규 가입: Supabase Auth에 계정 생성
            SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
            SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

            if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
                print("[kakao] missing SUPABASE_URL or SUPABASE_SERVICE_KEY")
                return self._redirect(f"{APP_BASE_URL}/login.html?error=server_config")

            headers = {
                "apikey": SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                "Content-Type": "application/json",
            }

            create_resp = req.post(
                f"{SUPABASE_URL}/auth/v1/admin/users",
                headers=headers,
                json={
                    "email": email,
                    "password": str(uuid.uuid4()),
                    "email_confirm": True,
                    "user_metadata": {"name": nickname, "role": "consumer"},
                },
                timeout=10,
            )

            user_id = None
            if create_resp.status_code in (200, 201):
                user_id = create_resp.json().get("id")
            else:
                # 이메일 중복이면 기존 유저 찾기
                print(f"[kakao] create user failed: {create_resp.status_code} {create_resp.text}")
                try:
                    user_list = req.get(
                        f"{SUPABASE_URL}/auth/v1/admin/users",
                        headers=headers,
                        timeout=10,
                    ).json()
                    users = user_list.get("users", [])
                    for u in users:
                        if u.get("email") == email:
                            user_id = u["id"]
                            break
                except Exception as e:
                    print(f"[kakao] user lookup failed: {e}")

            # profiles에 kakao_id 저장
            if user_id:
                try:
                    db.table("profiles").update({"kakao_id": kakao_id, "name": nickname}).eq("id", user_id).execute()
                except Exception as e:
                    print(f"[kakao] profile update failed: {e}")

            # 프론트엔드로 리다이렉트
            self._redirect(f"{APP_BASE_URL}/login.html?kakao_token=done&email={email}")

        except Exception as e:
            print(f"[kakao] unhandled error: {e}")
            traceback.print_exc()
            self._redirect(f"{APP_BASE_URL}/login.html?error=kakao_server")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def _redirect(self, url):
        self.send_response(302)
        self.send_header("Location", url)
        self.end_headers()

    def log_message(self, *_): pass
