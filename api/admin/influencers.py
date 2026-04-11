"""
GET  /api/admin/influencers  — 신청 목록
PUT  /api/admin/influencers  — 승인/거절
"""
from http.server import BaseHTTPRequestHandler
import json, datetime
from api._db import get_db, ok, err
from api._auth import require_admin


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self): self._cors()

    def do_GET(self):
        admin, _ = require_admin(self.headers)
        if not admin:
            return self._send(*err("관리자 권한 필요", 403))

        from urllib.parse import urlparse, parse_qs
        qs     = parse_qs(urlparse(self.path).query)
        status = qs.get("status", ["pending"])[0]

        db = get_db()
        result = db.table("influencer_applications") \
            .select("*, profiles(name, phone)") \
            .eq("status", status) \
            .order("created_at", desc=True) \
            .execute()

        self._send(*ok(result.data or []))

    def do_PUT(self):
        admin, _ = require_admin(self.headers)
        if not admin:
            return self._send(*err("관리자 권한 필요", 403))

        body           = self._body()
        application_id = body.get("application_id")
        action         = body.get("action")   # "approve" | "reject"
        reason         = body.get("reason", "")

        if action not in ("approve", "reject"):
            return self._send(*err("action은 approve 또는 reject"))

        db = get_db()
        app = db.table("influencer_applications").select("*").eq("id", application_id).single().execute()
        if not app.data:
            return self._send(*err("신청을 찾을 수 없습니다"))

        application = app.data
        now = datetime.datetime.utcnow().isoformat()

        if action == "approve":
            # 프로필 role 변경
            db.table("profiles").update({
                "role": "influencer",
                "channel_name": application.get("channel_name", ""),
            }).eq("id", application["user_id"]).execute()

            # 신청 상태 업데이트
            db.table("influencer_applications").update({
                "status":      "approved",
                "reviewed_at": now,
                "reviewed_by": str(admin.id),
            }).eq("id", application_id).execute()

            # 알림
            db.table("notifications").insert({
                "user_id": application["user_id"],
                "type":    "application_approved",
                "title":   "🎉 인플루언서 신청이 승인됐어요!",
                "content": "이제 공구를 등록하고 판매를 시작할 수 있어요.",
                "link":    "/influencer-dashboard.html",
                "is_read": False,
            }).execute()

        else:
            db.table("influencer_applications").update({
                "status":           "rejected",
                "rejection_reason": reason,
                "reviewed_at":      now,
                "reviewed_by":      str(admin.id),
            }).eq("id", application_id).execute()

            db.table("notifications").insert({
                "user_id": application["user_id"],
                "type":    "application_rejected",
                "title":   "인플루언서 신청 결과",
                "content": f"아쉽게도 이번 신청은 승인되지 않았어요. 사유: {reason}",
                "link":    "/influencer-apply.html",
                "is_read": False,
            }).execute()

        self._send(*ok({"action": action}))

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n)) if n else {}

    def _cors(self):
        self.send_response(204)
        for k, v in {"Access-Control-Allow-Origin":"*","Access-Control-Allow-Headers":"Content-Type,Authorization","Access-Control-Allow-Methods":"GET,PUT,OPTIONS"}.items():
            self.send_header(k, v)
        self.end_headers()

    def _send(self, body, status=200, headers=None):
        self.send_response(status)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body.encode() if isinstance(body, str) else body)

    def log_message(self, *_): pass
