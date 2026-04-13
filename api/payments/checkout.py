"""
POST /api/payments/checkout
Body: { gugu_id, quantity, shipping, payment_method('card'|'bank_transfer'), bank_depositor? }

- card: Toss 결제 파라미터 반환
- bank_transfer: 주문 즉시 pending 저장, 계좌정보 반환
"""
from http.server import BaseHTTPRequestHandler
import json, os, uuid, datetime
from api._db import get_db, ok, err
from api._auth import get_user_with_profile

# 무통장입금 계좌 정보 (환경변수 또는 하드코딩)
BANK_INFO = {
    "bank":    os.environ.get("BANK_NAME",    "국민은행"),
    "account": os.environ.get("BANK_ACCOUNT", "000000-00-000000"),
    "holder":  os.environ.get("BANK_HOLDER",  "GUGU(구구)"),
}


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self): self._cors()

    def do_POST(self):
        body = self._body()
        user, profile = get_user_with_profile(self.headers)
        if not user:
            return self._send(*err("로그인이 필요합니다", 401))

        gugu_id        = body.get("gugu_id")
        quantity       = int(body.get("quantity", 1))
        shipping       = body.get("shipping", {})
        payment_method = body.get("payment_method", "card")  # card | bank_transfer
        bank_depositor = body.get("bank_depositor", profile.get("name", "")).strip()

        db = get_db()

        # 공구 정보 조회
        g = db.table("gugus").select("*").eq("id", gugu_id).eq("status", "active").single().execute()
        if not g.data:
            return self._send(*err("공구를 찾을 수 없습니다"))

        gugu = g.data
        unit_price   = int(gugu["sale_price"])
        total_amount = unit_price * quantity

        # 수량형 공구: 남은 자리 체크
        gugu_type = gugu.get("gugu_type", "period")
        if gugu_type == "quantity":
            remain = gugu["target_participants"] - gugu["current_participants"]
            if quantity > remain:
                return self._send(*err(f"남은 자리가 {remain}개밖에 없어요"))

        order_id = f"GUGU-{uuid.uuid4().hex[:16].upper()}"

        order_data = {
            "id":             str(uuid.uuid4()),
            "gugu_id":        gugu_id,
            "consumer_id":    user.id,
            "quantity":       quantity,
            "unit_price":     unit_price,
            "total_amount":   total_amount,
            "payment_method": payment_method,
            "status":         "pending",
        }
        order_data["toss_order_id"] = order_id
        # 선택 컬럼 — DB에 있을 때만 추가 (없으면 PostgREST가 42703 에러)
        if shipping.get("name"):    order_data["shipping_name"]    = shipping["name"]
        if shipping.get("phone"):   order_data["shipping_phone"]   = shipping["phone"]
        if shipping.get("address"): order_data["shipping_address"] = shipping["address"]
        if shipping.get("zipcode"): order_data["shipping_zip"]     = shipping["zipcode"]
        # toss_order_id 컬럼이 DB에 있으면 저장 (없으면 skip)
        _toss_order_id = order_id

        gugu_title = (gugu.get("product_name") or gugu.get("title") or "상품")[:100]

        if payment_method == "bank_transfer":
            order_data["bank_depositor"] = bank_depositor
            try:
                order = db.table("orders").insert(order_data).execute()
            except Exception:
                # shipping 컬럼 없는 경우 기본 필드만으로 재시도
                base = {k: v for k, v in order_data.items()
                        if k in ("id","gugu_id","consumer_id","quantity","unit_price",
                                 "total_amount","payment_method","status","bank_depositor")}
                order = db.table("orders").insert(base).execute()
            return self._send(*ok({
                "payment_method": "bank_transfer",
                "order_id":       _toss_order_id,
                "order_db_id":    order.data[0]["id"],
                "amount":         total_amount,
                "order_name":     gugu_title,
                "bank":           BANK_INFO["bank"],
                "account":        BANK_INFO["account"],
                "holder":         BANK_INFO["holder"],
                "depositor":      bank_depositor or profile.get("name", ""),
                "deadline":       (datetime.datetime.utcnow() + datetime.timedelta(hours=24)).strftime("%Y-%m-%d %H:%M"),
            }))

        # 카드: 주문 초안만 저장, Toss 파라미터 반환
        try:
            order = db.table("orders").insert(order_data).execute()
        except Exception:
            base = {k: v for k, v in order_data.items()
                    if k in ("id","gugu_id","consumer_id","quantity","unit_price",
                             "total_amount","payment_method","status")}
            order = db.table("orders").insert(base).execute()

        imp_code = os.environ.get("IMP_CODE", "imp15482145")
        self._send(*ok({
            "payment_method":  "card",
            "order_id":        _toss_order_id,
            "order_db_id":     order.data[0]["id"],
            "amount":          total_amount,
            "order_name":      gugu_title,
            "customer_name":   profile.get("name", ""),
            "customer_email":  getattr(user, "email", "") or "",
            "imp_code":        imp_code,
        }))

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n)) if n else {}

    def _cors(self):
        self.send_response(204)
        for k, v in {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
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
