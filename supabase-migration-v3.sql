-- =============================================
-- GUGU. Supabase Migration v3
-- 브랜드사 연결: gugus 테이블에 brand 필드 추가
-- 실행: Supabase SQL Editor에서 실행
-- =============================================

-- 1. gugus 테이블에 브랜드 필드 추가
ALTER TABLE gugus
  ADD COLUMN IF NOT EXISTS brand_name  TEXT,
  ADD COLUMN IF NOT EXISTS brand_email TEXT,
  ADD COLUMN IF NOT EXISTS brand_token TEXT;

-- 2. 기존 공구에 brand_token 자동 생성 (pgcrypto 없는 경우 gen_random_uuid 사용)
UPDATE gugus
SET brand_token = gen_random_uuid()::text
WHERE brand_token IS NULL;

-- 3. 인덱스 (토큰 조회 최적화)
CREATE UNIQUE INDEX IF NOT EXISTS idx_gugus_brand_token ON gugus(brand_token)
  WHERE brand_token IS NOT NULL;

-- 4. RLS: 브랜드 토큰으로 공구 + 주문 조회 허용
-- orders 테이블에서 gugu 소유자가 아닌 브랜드도 읽기 가능하도록
-- (서비스 롤 클라이언트로 API에서 처리하므로 RLS 별도 추가 불필요)

SELECT 'Migration v3 완료 — brand_name, brand_email, brand_token 추가' AS result;
