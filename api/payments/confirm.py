"""
POST /api/payments/confirm
PortOne 결제 완료 후 서버 검증 + 주문 확정
Body: { imp_uid, merchant_uid, amount }
"""
from http.server import BaseHTTPRequestHandler
import json, os, datetime
import requests as req
from api._db import get_db, ok, err
from api._auth import get_user_with_profile

PORTONE_API_KEY = os.environ.get("PORTONE_API_KEY") or os.environ.get("IMP_KEY", "")
PORTONE_API_SECRET = os.environ.get("PORTONE_API_SECRET") or os.environ.get("IMP_SECRET", "")


def _get_portone_token():
    """PortOne 액세스 토큰 발급"""
    resp = req.post(
        "https://api.iamport.kr/users/getToken",
        json={"imp_key": PORTONE_API_KEY, "imp_secret": PORTONE_API_SECRET},
        timeout=10,
    )
    if resp.status_code != 200:
        return None
    data = resp.json()
    if data.get("code") != 0:
        return None
    return data["response"]["access_token"]


def _get_payment_info(access_token, imp_uid):
    """PortOne에서 결제 정보 조회"""
    resp = req.get(
        f"https://api.iamport.kr/payments/{imp_uid}",
        headers={"Authorization": access_token},
        timeout=10,
    )
    if resp.status_code != 200:
        return None
    data = resp.json()
    if data.get("code") != 0:
        return None
    return data["response"]


def _find_payment_by_merchant_uid(access_token, merchant_uid, status="paid"):
    """Look up a PortOne payment by merchant_uid when the browser callback is missed."""
    resp = req.get(
        f"https://api.iamport.kr/payments/find/{merchant_uid}/{status}",
        headers={"Authorization": access_token},
        timeout=10,
    )
    if resp.status_code != 200:
        return None
    data = resp.json()
    if data.get("code") != 0:
        return None
    return data["response"]


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self._cors()

    def do_POST(self):
        body = self._body()
        user, profile = get_user_with_profile(self.headers)
        if not user:
            return self._send(*err("로그인이 필요합니다", 401))

        imp_uid      = body.get("imp_uid")
        merchant_uid = body.get("merchant_uid")  # order_id (GUGU-XXXX)
        amount       = int(body.get("amount", 0))

        if not all([merchant_uid, amount]):
            return self._send(*err("필수 파라미터 누락"))

        db = get_db()

        # DB에서 주문 조회 (금액 위변조 방지)
        # merchant_uid로 조회 시도 (toss_order_id 컬럼)
        order = None
        try:
            o = db.table("orders").select("*").eq("toss_order_id", merchant_uid).eq("consumer_id", user.id).single().execute()
            order = o.data
        except Exception:
            pass

        if not order:
            # toss_order_id 컬럼이 없는 경우 consumer_id + pending 으로 최근 주문 조회
            try:
                o = db.table("orders").select("*").eq("consumer_id", user.id).eq("status", "pending").order("created_at", desc=True).limit(1).execute()
                if o.data:
                    order = o.data[0]
            except Exception:
                pass

        if not order:
            return self._send(*err("주문을 찾을 수 없습니다"))

        if order["total_amount"] != amount:
            return self._send(*err("금액 불일치 — 결제 거부", 400))
        if order["status"] == "paid":
            return self._send(*ok({"order_id": order["id"], "status": "paid"}))
        if order["status"] != "pending":
            return self._send(*err("이미 처리된 주문입니다"))

        # PortOne 서버 검증
        access_token = _get_portone_token()
        if not access_token:
            return self._send(*err("결제 검증 실패: 토큰 발급 오류"))

        payment = _get_payment_info(access_token, imp_uid) if imp_uid else _find_payment_by_merchant_uid(access_token, merchant_uid)
        if not payment:
            return self._send(*err("결제 검증 실패: 결제 정보 조회 오류"))

        # 금액 일치 확인
        imp_uid = payment.get("imp_uid") or imp_uid

        if payment["amount"] != amount:
            return self._send(*err(f"결제 금액 불일치: 요청 {amount} vs 실제 {payment['amount']}"))

        if payment["status"] != "paid":
            return self._send(*err(f"결제 상태 이상: {payment['status']}"))

        pay_method = payment.get("pay_method", "card")

        # 결제 레코드 저장
        try:
            db.table("payments").insert({
                "order_id":       order["id"],
                "payment_key":    imp_uid,
                "toss_order_id":  merchant_uid,
                "payment_method": pay_method,
                "amount":         amount,
                "status":         "done",
                "raw_response":   json.dumps(payment, ensure_ascii=False, default=str),
            }).execute()
        except Exception as e:
            print(f"[confirm] payment insert error: {e}")

        # 주문 상태 업데이트
        db.table("orders").update({
            "status":      "paid",
            "paid_at":     datetime.datetime.utcnow().isoformat(),
            "payment_key": imp_uid,
        }).eq("id", order["id"]).execute()

        # 참여자 수 증가
        try:
            db.rpc("increment_participants", {"p_gugu_id": order["gugu_id"]}).execute()
        except Exception as e:
            print(f"[confirm] increment error: {e}")

        # 인플루언서에게 알림
        try:
            gugu = db.table("gugus").select("influencer_id, title").eq("id", order["gugu_id"]).single().execute().data
            if gugu:
                gugu_title = (gugu.get("title") or "상품")[:30]
                db.table("notifications").insert({
                    "user_id": gugu["influencer_id"],
                    "type":    "new_order",
                    "title":   "새 주문이 들어왔어요",
                    "content": f"{profile.get('name','소비자')}님이 [{gugu_title}]을 주문했어요",
                    "link":    "/influencer-dashboard.html",
                    "is_read": False,
                }).execute()
        except Exception as e:
            print(f"[confirm] notification error: {e}")

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
