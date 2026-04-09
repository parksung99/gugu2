# GUGU. 프로젝트 컨텍스트

## 프로젝트 개요
인플루언서 공동구매(공구) 플랫폼. 소비자가 인플루언서의 공구 아이템을 구매하는 구조.

## 기술 스택
- **프론트엔드**: 순수 HTML + CSS + Vanilla JS (`.html` 파일들)
- **백엔드**: Vercel Python 서버리스 함수 (`api/*.py`)
- **DB**: Supabase (PostgreSQL + RLS + Realtime)
- **결제**: 토스페이먼츠 v1
- **배포**: Vercel (GitHub 자동 배포) → `github.com/parksung99/gugu2`
- **소셜 로그인**: Kakao (`/api/auth/kakao`), Google (Supabase OAuth)

## 역할 구조
- `consumer` — 공구 구매자 (기본값)
- `influencer` — 공구 등록자 (admin이 승인해야 role 변경)
- `admin` — 전체 관리 (`UPDATE profiles SET role='admin' WHERE email='...'`)

## 주요 파일 구조
```
api/
  _db.py          # Supabase 서비스롤 클라이언트, ok()/err() 헬퍼
  _auth.py        # get_user(), require_admin() JWT 검증
  payments/
    checkout.py   # POST: 주문 초안 생성, Toss 결제 파라미터 반환
    confirm.py    # POST: Toss 결제 확인, orders 저장
  orders/
    list.py       # GET: 내 주문 목록
    cancel.py     # POST: 주문 취소 + Toss 취소 API
  admin/
    orders.py     # GET: 전체 주문 / GET?stats=1: 대시보드 통계 / PUT: 상태변경+송장
    influencers.py # GET: 신청 목록 / PUT: 승인(role=influencer)/거절
  influencers/
    apply.py      # POST: 인플루언서 신청 (influencer_applications 테이블)
  gugus/
    manage.py     # POST: 공구 등록 / PUT: 수정 / DELETE: 삭제
  follows/
    toggle.py     # POST: 팔로우/언팔로우 토글
  notifications/
    list.py       # GET: 알림 목록 / POST: 읽음 처리
  auth/
    kakao.py      # GET: 카카오 OAuth 중계

js/
  supabase.js     # sb 클라이언트, getCurrentUser(), formatKRW(), daysLeft() 등
  nav.js          # 공통 네비게이션 로그인 상태 반영

주요 HTML:
  index.html              # 메인홈 (Supabase에서 gugus 로드)
  product-detail.html     # 상품 상세 (?id=GUGU_ID)
  checkout.html           # 결제 (?gugu_id=ID&qty=N) → 토스페이먼츠
  order-complete.html     # 결제 완료 (paymentKey/orderId/amount URL파라미터)
  mypage.html             # 주문내역, 프로필
  notifications.html      # 실시간 알림 (Supabase Realtime)
  admin.html              # 관리자 패널 (주문관리, 인플루언서 승인)
  influencer-dashboard.html # 인플루언서 대시보드
  influencer-apply.html   # 인플루언서 신청 폼
  open-gugu.html          # 공구 등록 (/api/gugus/manage POST)
```

## DB 스키마 핵심
- `profiles`: id, name, email, role, channel_name, phone
- `gugus`: id, influencer_id, title, emoji, original_price, sale_price, target_participants, current_participants, status, end_date
- `orders`: id, toss_order_id, gugu_id, consumer_id, quantity, unit_price, total_amount, status, shipping_*, tracking_number, payment_key
- `influencer_applications`: id, user_id, channel_name, status(pending/approved/rejected)
- `notifications`: id, user_id, type, title, content, link, is_read
- `follows`, `payments`, `settlements`

RPC 함수: `increment_participants(p_gugu_id)`, `decrement_participants(p_gugu_id)`

## 중요 규칙
- `formatKRW(value)` → 이미 '원' 포함. 템플릿에서 `${formatKRW(x)}원` 쓰면 안됨
- `daysLeft(endDate)` → date string을 받음. gugu 객체 넘기면 안됨
- gugus 테이블 컬럼명: `title` (product_name 아님)
- Vercel Hobby 플랜: 서버리스 함수 최대 12개 (현재 11개)

## Vercel 환경변수 (설정 필요)
- SUPABASE_URL, SUPABASE_SERVICE_KEY
- TOSS_CLIENT_KEY, TOSS_SECRET_KEY
- KAKAO_CLIENT_ID, KAKAO_CLIENT_SECRET
- APP_BASE_URL (예: https://gugu2.vercel.app)

## 결제 흐름
1. `product-detail.html` 구매 버튼 → `checkout.html?gugu_id=ID&qty=N`
2. `checkout.html` → `/api/payments/checkout` POST → 주문 초안(pending) 생성
3. 토스페이먼츠 `requestPayment()` → 결제창
4. 성공 → `order-complete.html?paymentKey=...&orderId=...&amount=...`
5. `order-complete.html` → `/api/payments/confirm` POST → DB 저장, status=paid
