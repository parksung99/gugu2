"""
POST /api/payments/confirm
Toss 결제 완료 후 서버 검증 + 주문 확정
Body: { paymentKey, orderId, amount }
"""
from http.server import BaseHTTPRequestHandler
import json, os, base64, datetime
import requests as req
from api._db import get_db, ok, err
from api._auth import get_user_with_profile

TOSS_SECRET_KEY = os.environ.get("TOSS_SECRET_KEY", "test_sk_zXLkKEypNArWmo50nX3lmeaxYG5R")
TOSS_CONFIRM_URL = "https://api.tosspayments.com/v1/payments/confirm"


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self._cors()

    def do_POST(self):
        body = self._body()
        user, profile = get_user_with_profile(self.headers)
        if not user:
            return self._send(*err("로그인이 필요합니다", 401))

        payment_key = body.get("paymentKey")
        order_id    = body.get("orderId")      # toss_order_id
        amount      = int(body.get("amount", 0))

        if not all([payment_key, order_id, amount]):
            return self._send(*err("필수 파라미터 누락"))

        db = get_db()

        # DB에서 주문 조회 (금액 위변조 방지)
        o = db.table("orders").select("*").eq("toss_order_id", order_id).eq("consumer_id", user.id).single().execute()
        if not o.data:
            return self._send(*err("주문을 찾을 수 없습니다"))

        order = o.data
        if order["total_amount"] != amount:
            return self._send(*err("금액 불일치 — 결제 거부", 400))
        if order["status"] != "pending":
            return self._send(*err("이미 처리된 주문입니다"))

        # Toss 서버 검증
        auth_bytes = base64.b64encode(f"{TOSS_SECRET_KEY}:".encode()).decode()
        toss_resp = req.post(
            TOSS_CONFIRM_URL,
            headers={
                "Authorization": f"Basic {auth_bytes}",
                "Content-Type": "application/json",
            },
            json={"paymentKey": payment_key, "orderId": order_id, "amount": amount},
            timeout=10,
        )

        if toss_resp.status_code != 200:
            toss_err = toss_resp.json()
            return self._send(*err(f"결제 실패: {toss_err.get('message', '알 수 없는 오류')}"))

        toss_data = toss_resp.json()
        method = toss_data.get("method", "")

        # 결제 레코드 저장
        db.table("payments").insert({
            "order_id":       order["id"],
            "payment_key":    payment_key,
            "toss_order_id":  order_id,
            "payment_method": method,
            "amount":         amount,
            "status":         "done",
            "raw_response":   json.dumps(toss_data, ensure_ascii=False),
        }).execute()

        # 주문 상태 업데이트
        db.table("orders").update({
            "status":      "paid",
            "paid_at":     datetime.datetime.utcnow().isoformat(),
            "payment_key": payment_key,
        }).eq("id", order["id"]).execute()

        # 참여자 수 증가
        db.rpc("increment_participants", {"p_gugu_id": order["gugu_id"]}).execute()

        # 인플루언서에게 알림
        gugu = db.table("gugus").select("influencer_id, product_name").eq("id", order["gugu_id"]).single().execute().data
        if gugu:
            gugu_title = (gugu.get("product_name") or gugu.get("title") or "상품")[:30]
            db.table("notifications").insert({
                "user_id": gugu["influencer_id"],
                "type":    "new_order",
                "title":   "새 주문이 들어왔어요 🛍️",
                "content": f"{profile.get('name','소비자')}님이 [{gugu_title}]을 주문했어요",
                "link":    f"/influencer-dashboard.html",
                "is_read": False,
            }).execute()

        self._send(*ok({"order_id": order["id"], "status": "paid"}))

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n)) if n else {}

    def _cors(self):
        self.send_response(204)
        for k, v in {"Access-Control-Allow-Origin":"*","Access-Control-Allow-Headers":"Content-Type,Authorization","Access-Control-Allow-Methods":"GET,POST,PUT,DELETE,OPTIONS"}.items():
            self.send_header(k, v)
        self.end_headers()

    def _send(self, body, status=200, headers=None):
        self.send_response(status)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body.encode() if isinstance(body, str) else body)

    def log_message(self, *_): pass
