// ============================================================
// GUGU — 공통 네비게이션 로그인 상태 반영
// 모든 페이지 </body> 직전에 아래처럼 포함하세요:
// <script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
// <script src="js/supabase.js"></script>
// <script src="js/nav.js"></script>
// ============================================================

(async function initNav() {
  const u = await getCurrentUser();

  // 로그인/회원가입 버튼 영역 찾기 (index.html 기준)
  const loginBtn  = document.getElementById('navLoginBtn');
  const signupBtn = document.getElementById('navSignupBtn');
  const userArea  = document.getElementById('navUserArea');

  if (!loginBtn && !userArea) return; // nav 요소 없으면 종료

  if (u) {
    // 로그인 상태 — 버튼 숨기고 아바타 + 이름 표시
    if (loginBtn)  loginBtn.style.display  = 'none';
    if (signupBtn) signupBtn.style.display = 'none';

    if (userArea) {
      const name = u.profile?.channel_name || u.profile?.name || '유저';
      const isInfluencer = u.profile?.role === 'influencer';
      const initial = name[0] || '?';

      userArea.style.display = 'flex';
      userArea.innerHTML = `
        <div onclick="location.href='${isInfluencer ? 'influencer-dashboard.html' : 'mypage.html'}'"
             style="display:flex;align-items:center;gap:8px;cursor:pointer;padding:4px 10px;border-radius:8px;border:1px solid var(--b1);background:var(--s2);transition:.15s"
             onmouseover="this.style.borderColor='var(--r)'" onmouseout="this.style.borderColor='var(--b1)'">
          <div style="width:26px;height:26px;border-radius:50%;background:linear-gradient(135deg,var(--r),var(--o));display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:#fff;flex-shrink:0">${initial}</div>
          <span style="font-size:13px;font-weight:600;color:var(--t);max-width:80px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${name}</span>
          ${isInfluencer ? '<span style="font-size:10px;color:var(--r);font-weight:700;background:rgba(255,59,59,0.1);padding:1px 6px;border-radius:4px">인플루언서</span>' : ''}
        </div>
        <button onclick="doSignOut()"
                style="padding:6px 12px;border-radius:7px;border:1px solid var(--b1);background:none;color:var(--t2);font-size:12px;cursor:pointer;font-family:inherit;transition:.15s"
                onmouseover="this.style.color='var(--t)'" onmouseout="this.style.color='var(--t2)'">
          로그아웃
        </button>
      `;
    }
  } else {
    // 비로그인 상태 — 버튼 표시
    if (loginBtn)  loginBtn.style.display  = '';
    if (signupBtn) signupBtn.style.display = '';
    if (userArea)  userArea.style.display  = 'none';
  }
})();

async function doSignOut() {
  await sb.auth.signOut();
  location.href = 'login.html';
}
