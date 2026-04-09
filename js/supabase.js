const SUPABASE_URL = 'https://yattlqdsnrqeqzvcuvuu.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlhdHRscWRzbnJxZXF6dmN1dnV1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzU0Mzc4NDMsImV4cCI6MjA5MTAxMzg0M30.OXYzBYsMHg3ryW7DDr5xljXrgCkL92EIQS2LunAabag';

const { createClient } = supabase;
const sb = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

async function getCurrentUser() {
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return null;

  const { data: profile } = await sb
    .from('profiles')
    .select('*')
    .eq('id', user.id)
    .single();

  return { ...user, profile };
}

function requireAuth(redirectTo = 'login.html') {
  getCurrentUser().then((user) => {
    if (!user) location.href = redirectTo;
  });
}

function requireInfluencer() {
  getCurrentUser().then((user) => {
    if (!user) {
      location.href = 'login.html';
      return;
    }

    if (user.profile?.role !== 'influencer') {
      location.href = 'index.html';
    }
  });
}

async function signOut() {
  await sb.auth.signOut();
  location.href = 'login.html';
}

async function getInfluencerGugus(influencerId) {
  const { data } = await sb
    .from('gugus')
    .select('*')
    .eq('influencer_id', influencerId)
    .order('created_at', { ascending: false });

  return data || [];
}

async function getInfluencerRevenue(influencerId) {
  const { data: gugus } = await sb
    .from('gugus')
    .select('id')
    .eq('influencer_id', influencerId);

  if (!gugus?.length) return { total: 0, thisMonth: 0 };

  const ids = gugus.map((gugu) => gugu.id);
  const startOfMonth = new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString();

  const { data: orders } = await sb
    .from('orders')
    .select('total_amount, created_at')
    .in('gugu_id', ids)
    .neq('status', 'cancelled')
    .neq('status', 'refunded');

  if (!orders?.length) return { total: 0, thisMonth: 0 };

  const total = orders.reduce((sum, order) => sum + Number(order.total_amount || 0), 0);
  const thisMonth = orders
    .filter((order) => order.created_at >= startOfMonth)
    .reduce((sum, order) => sum + Number(order.total_amount || 0), 0);

  return { total, thisMonth };
}

async function getGuguOrders(guguId) {
  const { data } = await sb
    .from('orders')
    .select('*')
    .eq('gugu_id', guguId)
    .order('created_at', { ascending: false });

  return data || [];
}

function formatKRW(value) {
  return `${Number(value || 0).toLocaleString('ko-KR')}원`;
}

function daysLeft(endDate) {
  if (!endDate) return '-';

  const diff = new Date(endDate) - new Date();
  const days = Math.ceil(diff / (1000 * 60 * 60 * 24));

  if (days < 0) return '마감';
  if (days === 0) return '오늘 마감';
  return `${days}일 남음`;
}

function progressPct(currentOrGugu, target) {
  if (typeof currentOrGugu === 'object' && currentOrGugu !== null) {
    const current = Number(currentOrGugu.current_participants || 0);
    const goal = Number(currentOrGugu.target_participants || 0);
    if (!goal) return 0;
    return Math.min(100, Math.round((current / goal) * 100));
  }

  const current = Number(currentOrGugu || 0);
  const goal = Number(target || 0);
  if (!goal) return 0;
  return Math.min(100, Math.round((current / goal) * 100));
}

function getDiscountRate(gugu) {
  const original = Number(gugu?.original_price || 0);
  const sale = Number(gugu?.sale_price || 0);
  if (!original || sale >= original) return 0;
  return Math.max(0, Math.round((1 - sale / original) * 100));
}

function getDisplayName(profile) {
  return profile?.channel_name || profile?.name || '인플루언서';
}

function getAvatarLetter(profile) {
  return getDisplayName(profile).trim().charAt(0) || 'G';
}

function isActiveGugu(gugu) {
  if (!gugu || gugu.status !== 'active') return false;
  if (!gugu.end_date) return true;
  return new Date(gugu.end_date) >= new Date(new Date().toDateString());
}

function getGuguStatusLabel(gugu) {
  if (!gugu) return '준비중';
  if (gugu.status === 'closed') return '종료';
  if (gugu.status === 'cancelled') return '취소';
  return isActiveGugu(gugu) ? '진행중' : '마감';
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
