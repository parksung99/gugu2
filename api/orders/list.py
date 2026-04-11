"""
GET /api/orders/list           — 소비자: 내 주문 목록
GET /api/orders/list?role=inf  — 인플루언서: 내 공구의 주문 목록
PUT /api/orders/list           — 인플루언서: 송장번호·상태 업데이트
"""
from http.server import BaseHTTPRequestHandler
import json, datetime
from api._db import get_db, ok, err
from api._auth import get_user_with_profile

STATUS_LABEL = {
    "paid": "결제완료", "preparing": "상품준비중",
    "shipped": "배송중", "delivered": "배송완료",
    "cancelled": "취소", "refunded": "환불"
}

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self): self._cors()

    def do_GET(self):
        user, profile = get_user_with_profile(self.headers)
        if not user:
            return self._send(*err("로그인 필요", 401))

        from urllib.parse import urlparse, parse_qs
        qs = parse_qs(urlparse(self.path).query)
        role = qs.get("role", [None])[0]
        status_filter = qs.get("status", [None])[0]

        db = get_db()

        # 인플루언서: 내 공구에 들어온 주문
        if role == "inf" or profile.get("role") == "influencer":
            # 내 공구 ID 목록
            my_gugus = db.table("gugus").select("id").eq("influencer_id", user.id).execute()
            gugu_ids = [g["id"] for g in (my_gugus.data or [])]
            if not gugu_ids:
                return self._send(*ok([]))

            q = db.table("orders").select(
                "*, gugus(id, product_name, emoji, category, sale_price, end_date), "
                "profiles!orders_consumer_id_fkey(name, phone)"
            ).in_("gugu_id", gugu_ids).order("created_at", desc=True)

            if status_filter:
                q = q.eq("status", status_filter)

            orders = q.execute()
            return self._send(*ok(orders.data or []))

        # 소비자: 내가 구매한 주문
        q = db.table("orders").select(
            "*, gugus(product_name, emoji, category, end_date, influencer_id, profiles(channel_name, name))"
        ).eq("consumer_id", user.id).order("created_at", desc=True)

        if status_filter:
            q = q.eq("status", status_filter)

        orders = q.execute()
        self._send(*ok(orders.data or []))

    def do_PUT(self):
        """인플루언서가 자신의 공구 주문에 송장번호·배송사·상태 업데이트"""
        user, profile = get_user_with_profile(self.headers)
        if not user:
            return self._send(*err("로그인 필요", 401))
        if profile.get("role") not in ("influencer", "admin"):
            return self._send(*err("인플루언서 권한 필요", 403))

        body = self._body()
        order_id         = body.get("order_id")
        tracking_number  = body.get("tracking_number", "").strip()
        shipping_carrier = body.get("shipping_carrier", "").strip()
        new_status       = body.get("status")

        if not order_id:
            return self._send(*err("order_id 필요"))

        db = get_db()

        # 본인 공구의 주문인지 확인
        order = db.table("orders").select(
            "id, status, consumer_id, gugu_id, gugus(influencer_id, product_name)"
        ).eq("id", order_id).single().execute().data

        if not order:
            return self._send(*err("주문 없음", 404))
        if order["gugus"]["influencer_id"] != user.id and profile.get("role") != "admin":
            return self._send(*err("권한 없음", 403))

        updates = {}
        if tracking_number:
            updates["tracking_number"] = tracking_number
        if shipping_carrier:
            updates["shipping_carrier"] = shipping_carrier
        if new_status and new_status in ("preparing", "shipped", "delivered"):
            updates["status"] = new_status
            if new_status == "shipped":
                updates["shipped_at"] = datetime.datetime.utcnow().isoformat()
            elif new_status == "delivered":
                updates["delivered_at"] = datetime.datetime.utcnow().isoformat()

        if not updates:
            return self._send(*err("업데이트할 내용 없음"))

        db.table("orders").update(updates).eq("id", order_id).execute()

        # 배송 시작 시 소비자 알림
        if updates.get("status") == "shipped":
            g = order.get("gugus") or {}
            title_str = (g.get("product_name") or g.get("title") or "상품")[:30]
            carrier = shipping_carrier or ""
            tracking = tracking_number or ""
            db.table("notifications").insert({
                "user_id": order["consumer_id"],
                "type":    "shipped",
                "title":   "📦 상품이 출발했어요!",
                "content": f"[{title_str}] {carrier} {tracking}",
                "link":    "/mypage.html",
                "is_read": False,
            }).execute()

        self._send(*ok({"updated": True}))

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n)) if n else {}

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
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body.encode() if isinstance(body, str) else body)

    def log_message(self, *_): pass
