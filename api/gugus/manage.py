"""
GET  /api/gugus/manage?brand_token=XXX  — 브랜드 포털 (인증 없음)
POST /api/gugus/manage  — 공구 등록 (인플루언서)
PUT  /api/gugus/manage  — 공구 수정
DELETE /api/gugus/manage — 공구 삭제 (미판매 시)
"""
from http.server import BaseHTTPRequestHandler
import json, uuid, datetime, secrets, os
from urllib.parse import urlparse, parse_qs
from api._db import get_db, ok, err
from api._auth import get_user_with_profile


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self): self._cors()

    # ─── 브랜드 포털: 토큰으로 공구 + 주문 조회 (로그인 불필요) ───
    def do_GET(self):
        self._cors_headers()
        qs = parse_qs(urlparse(self.path).query)
        brand_token = qs.get("brand_token", [None])[0]
        if not brand_token:
            return self._send(*err("brand_token 파라미터 필요"))

        db = get_db()
        g = db.table("gugus").select(
            "id,title,emoji,category,sale_price,original_price,"
            "current_participants,target_participants,status,end_date,"
            "gugu_type,brand_name,brand_email,brand_token"
        ).eq("brand_token", brand_token).execute()

        if not g.data:
            return self._send(*err("유효하지 않은 브랜드 토큰", 404))

        gugu = g.data[0]

        orders = db.table("orders").select(
            "id,quantity,unit_price,total_amount,status,created_at,"
            "shipping_name,shipping_phone,shipping_address,shipping_detail,"
            "shipping_zip,tracking_number,shipping_carrier,payment_method"
        ).eq("gugu_id", gugu["id"]).neq("status", "cancelled").order(
            "created_at", desc=True
        ).execute()

        total_orders = len(orders.data or [])
        total_amount = sum(o.get("total_amount", 0) for o in (orders.data or []))
        pending_ship = sum(1 for o in (orders.data or []) if o.get("status") in ("paid", "preparing"))

        self._send(*ok({
            "gugu": {
                "title":                gugu["title"],
                "emoji":                gugu.get("emoji", "🛍️"),
                "category":             gugu.get("category", ""),
                "sale_price":           gugu["sale_price"],
                "original_price":       gugu["original_price"],
                "current_participants": gugu["current_participants"],
                "target_participants":  gugu["target_participants"],
                "status":               gugu["status"],
                "end_date":             gugu.get("end_date", ""),
                "gugu_type":            gugu.get("gugu_type", "period"),
                "brand_name":           gugu.get("brand_name", ""),
                "brand_email":          gugu.get("brand_email", ""),
                "brand_token":          gugu.get("brand_token", ""),
            },
            "summary": {
                "total_orders":  total_orders,
                "total_amount":  total_amount,
                "pending_ship":  pending_ship,
            },
            "orders": orders.data or [],
        }))

    def do_POST(self):
        user, profile = get_user_with_profile(self.headers)
        if not user:
            return self._send(*err("로그인 필요", 401))
        if not profile or profile.get("role") != "influencer":
            return self._send(*err("인플루언서만 등록 가능합니다", 403))

        body = self._body()
        required = ["title", "original_price", "sale_price", "target_participants", "end_date", "category"]
        for f in required:
            if not body.get(f):
                return self._send(*err(f"{f} 필드 누락"))

        original = int(body["original_price"])
        sale     = int(body["sale_price"])
        if sale >= original:
            return self._send(*err("공구가는 원가보다 낮아야 합니다"))

        gugu_type = body.get("gugu_type", "period")
        if gugu_type not in ("period", "quantity", "funding"):
            gugu_type = "period"

        db = get_db()
        start_date = body.get("start_date") or datetime.datetime.utcnow().isoformat()
        gugu = db.table("gugus").insert({
            "id":                   str(uuid.uuid4()),
            "influencer_id":        user.id,
            "title":                body["title"],
            "description":          body.get("description", ""),
            "category":             body["category"],
            "emoji":                body.get("emoji", "🛍️"),
            "original_price":       original,
            "sale_price":           sale,
            "target_participants":  int(body["target_participants"]),
            "min_participants":     int(body.get("min_participants", 0)),
            "current_participants": 0,
            "status":               "active",
            "gugu_type":            gugu_type,
            "brand_name":           body.get("brand_name", ""),
            "brand_email":          body.get("brand_email", ""),
            "brand_token":          secrets.token_urlsafe(24),
            "start_date":           start_date,
            "end_date":             body["end_date"],
        }).execute()
        row = gugu.data[0] if gugu.data else {}
        app_base = os.getenv("APP_BASE_URL", "").rstrip("/")
        if row.get("brand_token"):
            row["brand_portal_url"] = (
                f"{app_base}/brand-portal.html?token={row['brand_token']}"
                if app_base else
                f"/brand-portal.html?token={row['brand_token']}"
            )
        self._send(*ok(row))

    def do_PUT(self):
        user, profile = get_user_with_profile(self.headers)
        if not user or not profile or profile.get("role") != "influencer":
            return self._send(*err("인플루언서 권한 필요", 403))

        body    = self._body()
        gugu_id = body.get("id") or body.get("gugu_id")
        if not gugu_id:
            return self._send(*err("id 누락"))

        db = get_db()
        existing = db.table("gugus").select("influencer_id, current_participants").eq("id", gugu_id).single().execute()
        if not existing.data or existing.data["influencer_id"] != user.id:
            return self._send(*err("수정 권한이 없습니다", 403))
        if existing.data["current_participants"] > 0:
            body.pop("original_price", None)
            body.pop("sale_price", None)

        allowed = {"title","description","category","emoji","target_participants",
                   "end_date","status","gugu_type","brand_name","brand_email"}
        updates = {k: v for k, v in body.items() if k in allowed}
        if not updates:
            return self._send(*err("수정할 필드 없음"))

        result = db.table("gugus").update(updates).eq("id", gugu_id).execute()
        self._send(*ok(result.data[0] if result.data else {}))

    def do_DELETE(self):
        user, profile = get_user_with_profile(self.headers)
        if not user or not profile or profile.get("role") != "influencer":
            return self._send(*err("인플루언서 권한 필요", 403))

        qs = parse_qs(urlparse(self.path).query)
        gugu_id = qs.get("id", [None])[0]
        if not gugu_id:
            try:
                body = self._body()
            except Exception:
                body = {}
            gugu_id = body.get("id") or body.get("gugu_id")
        if not gugu_id:
            return self._send(*err("id 누락"))

        db = get_db()
        existing = db.table("gugus").select("influencer_id, current_participants").eq("id", gugu_id).single().execute()
        if not existing.data or existing.data["influencer_id"] != user.id:
            return self._send(*err("삭제 권한 없음", 403))
        if existing.data["current_participants"] > 0:
            return self._send(*err("참여자가 있는 공구는 삭제할 수 없어요. 종료 처리 후 삭제하세요."))

        db.table("gugus").delete().eq("id", gugu_id).execute()
        self._send(*ok({"deleted": True}))

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n)) if n else {}

    def _cors_headers(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Type", "application/json")
        self.end_headers()

    def _cors(self):
        self.send_response(204)
        for k, v in {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS"
        }.items():
            self.send_header(k, v)
        self.end_headers()

    def _send(self, body, status=200, headers=None):
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Type", "application/json")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body.encode() if isinstance(body, str) else body)

    def log_message(self, *_): pass
