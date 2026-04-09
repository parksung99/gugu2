(function () {
  const page = location.pathname.split('/').pop();

  window.addEventListener('load', () => {
    if (!window.sb) return;

    if (page === 'index.html' || page === '') initIndexPage();
    if (page === 'category.html') initCategoryPage();
    if (page === 'search.html') initSearchPage();
    if (page === 'product-detail.html') initProductDetailPage();
    if (page === 'influencer-profile.html') initInfluencerProfilePage();
  });

  function q(selector) {
    return document.querySelector(selector);
  }

  function qa(selector) {
    return [...document.querySelectorAll(selector)];
  }

  function getFallbackLabel(index) {
    return ['IMG', 'NEW', 'HOT', 'BAG', 'LIFE', 'CARE'][index % 6];
  }

  function renderMedia(imageUrl, alt, fallback, style = '') {
    if (imageUrl) {
      return `<img src="${escapeHtml(imageUrl)}" alt="${escapeHtml(alt)}" style="width:100%;height:100%;object-fit:cover;${style}">`;
    }
    return fallback;
  }

  async function fetchActiveGugus() {
    const { data } = await sb
      .from('gugus')
      .select('*, profiles!gugus_influencer_id_fkey(id, name, channel_name, follower_count, avatar_url, channel_url)')
      .order('created_at', { ascending: false });

    return (data || []).filter(isActiveGugu);
  }

  async function initIndexPage() {
    const gugus = await fetchActiveGugus();
    if (!gugus.length) return;

    const top = [...gugus].sort((a, b) => (b.current_participants || 0) - (a.current_participants || 0));
    const newest = [...gugus].sort((a, b) => new Date(b.created_at) - new Date(a.created_at)).slice(0, 6);
    const endingSoon = [...gugus]
      .filter((gugu) => gugu.end_date)
      .sort((a, b) => new Date(a.end_date) - new Date(b.end_date))
      .slice(0, 3);

    const badge = q('.hero-badge');
    if (badge) badge.innerHTML = `<span class="live-dot"></span>지금 ${gugus.length}개 공구 진행 중`;

    const hero = q('.hero-card');
    if (hero && top[0]) {
      const gugu = top[0];
      hero.innerHTML = `
        <div class="hc-img">${renderMedia(gugu.image_url, gugu.product_name, 'IMG')}<div class="hc-badge">${progressPct(gugu) >= 80 ? '마감임박' : '진행중'}</div></div>
        <div class="hc-body">
          <div class="hc-inf">
            <div class="av" style="background:var(--r)">${escapeHtml(getAvatarLetter(gugu.profiles))}</div>
            <div class="hc-name-row">
              <div class="hc-inf-name">${escapeHtml(getDisplayName(gugu.profiles))}</div>
              <div class="hc-inf-sub">${escapeHtml(gugu.category || '공구')}</div>
            </div>
            <div class="verified">인증</div>
          </div>
          <div class="hc-title">${escapeHtml(gugu.product_name)}</div>
          <div class="price-row">
            <span class="p-orig">${formatKRW(gugu.original_price)}</span>
            <span class="p-sale">${formatKRW(gugu.sale_price)}</span>
            <span class="p-disc">-${getDiscountRate(gugu)}%</span>
          </div>
          <div class="prog-lbl">
            <span>${Number(gugu.current_participants || 0).toLocaleString('ko-KR')}명 참여</span>
            <span style="color:var(--r)">${escapeHtml(daysLeft(gugu.end_date))}</span>
          </div>
          <div class="prog-bar"><div class="prog-fill" style="width:${progressPct(gugu)}%"></div></div>
          <button class="btn-buy" onclick="location.href='product-detail.html?id=${gugu.id}'">지금 참여하기</button>
          <div class="timer-row">종료까지 <span class="tc">${escapeHtml(daysLeft(gugu.end_date))}</span></div>
        </div>`;
    }

    const strip = q('.inf-strip');
    if (strip) {
      const seen = new Set();
      strip.innerHTML = top.filter((gugu) => {
        if (seen.has(gugu.influencer_id)) return false;
        seen.add(gugu.influencer_id);
        return true;
      }).slice(0, 10).map((gugu, index) => `
        <a class="inf-chip ${index < 2 ? 'live' : ''}" href="influencer-profile.html?id=${gugu.influencer_id}">
          <div class="ic-av">${escapeHtml(getAvatarLetter(gugu.profiles))}${index < 2 ? '<div class="ic-live"></div>' : ''}</div>
          <div class="ic-name">${escapeHtml(getDisplayName(gugu.profiles))}</div>
          <div class="ic-cnt">공구 보기</div>
        </a>
      `).join('');
    }

    const flash = q('.flash-grid');
    if (flash) {
      flash.innerHTML = (endingSoon.length ? endingSoon : top.slice(0, 3)).map((gugu, index) => `
        <a class="flash-card" href="product-detail.html?id=${gugu.id}">
          <div class="fc-img">${renderMedia(gugu.image_url, gugu.product_name, getFallbackLabel(index))}</div>
          <div class="fc-info">
            <div class="fc-inf">${escapeHtml(getDisplayName(gugu.profiles))} · ${escapeHtml(gugu.category || '공구')}</div>
            <div class="fc-name">${escapeHtml(gugu.product_name)}</div>
            <div class="fc-pr">
              <span class="fc-orig">${formatKRW(gugu.original_price)}</span>
              <span class="fc-sale">${formatKRW(gugu.sale_price)}</span>
              <span class="fc-disc">-${getDiscountRate(gugu)}%</span>
            </div>
            <div class="fc-bar"><div class="fc-fill" style="width:${progressPct(gugu)}%"></div></div>
            <div class="fc-meta">${Number(gugu.current_participants || 0).toLocaleString('ko-KR')}명 · ${escapeHtml(daysLeft(gugu.end_date))}</div>
          </div>
        </a>
      `).join('');
    }

    const newestGrid = q('.new-grid');
    if (newestGrid) {
      newestGrid.innerHTML = newest.map((gugu, index) => `
        <a class="new-card" href="product-detail.html?id=${gugu.id}">
          <div class="nc-img">${renderMedia(gugu.image_url, gugu.product_name, getFallbackLabel(index))}<div class="nc-new">NEW</div></div>
          <div class="nc-info">
            <div class="nc-inf">${escapeHtml(getDisplayName(gugu.profiles))} · ${escapeHtml(gugu.category || '공구')}</div>
            <div class="nc-name">${escapeHtml(gugu.product_name)}</div>
            <div class="nc-pr">
              <span class="nc-orig">${formatKRW(gugu.original_price)}</span>
              <span class="nc-sale">${formatKRW(gugu.sale_price)}</span>
              <span class="nc-disc">-${getDiscountRate(gugu)}%</span>
            </div>
            <div class="nc-time"><span class="nc-dot"></span>${escapeHtml(daysLeft(gugu.end_date))}</div>
          </div>
        </a>
      `).join('');
    }

    const categoryTabs = qa('.ct');
    const hotGrid = q('.prod-grid');
    const renderHot = (category) => {
      if (!hotGrid) return;
      let list = [...gugus];
      if (category !== '전체') list = list.filter((gugu) => gugu.category === category);
      list = list.sort((a, b) => (b.current_participants || 0) - (a.current_participants || 0)).slice(0, 8);
      hotGrid.innerHTML = list.map((gugu, index) => `
        <a class="prod-card" href="product-detail.html?id=${gugu.id}">
          <div class="pc-img">${renderMedia(gugu.image_url, gugu.product_name, getFallbackLabel(index))}
            <div class="pc-bdg ${progressPct(gugu) >= 80 ? 'bdg-r' : 'bdg-o'}">${progressPct(gugu) >= 80 ? '마감임박' : 'BEST'}</div>
          </div>
          <div class="pc-body">
            <div class="pc-inf-row">
              <div class="pc-av" style="background:#e83e8c">${escapeHtml(getAvatarLetter(gugu.profiles))}</div>
              <span class="pc-inf-name">${escapeHtml(getDisplayName(gugu.profiles))}</span>
            </div>
            <div class="pc-name">${escapeHtml(gugu.product_name)}</div>
            <div class="pc-pr">
              <span class="pc-orig">${formatKRW(gugu.original_price)}</span>
              <span class="pc-sale">${formatKRW(gugu.sale_price)}</span>
              <span class="pc-disc">-${getDiscountRate(gugu)}%</span>
            </div>
            <div class="pc-bar"><div class="pc-fill" style="width:${progressPct(gugu)}%"></div></div>
            <div class="pc-meta"><span>${Number(gugu.current_participants || 0).toLocaleString('ko-KR')}명</span><span>${escapeHtml(daysLeft(gugu.end_date))}</span></div>
          </div>
        </a>
      `).join('') || '<div style="grid-column:1/-1;text-align:center;color:var(--t2);padding:40px">표시할 공구가 없어요.</div>';
    };

    categoryTabs.forEach((tab) => {
      tab.onclick = () => {
        categoryTabs.forEach((item) => item.classList.remove('on'));
        tab.classList.add('on');
        renderHot(tab.textContent.trim());
      };
    });
    renderHot('전체');
  }

  async function initCategoryPage() {
    const gugus = await fetchActiveGugus();
    const params = new URLSearchParams(location.search);
    let currentCategory = params.get('category') || '뷰티';
    const grid = q('.product-grid');
    const tabs = qa('.sub-tab');

    const render = () => {
      const filtered = currentCategory === '전체' ? gugus : gugus.filter((gugu) => gugu.category === currentCategory);
      const title = q('.cat-title');
      if (title) title.textContent = currentCategory;
      qa('.result-count strong, .cat-count strong').forEach((el) => {
        el.textContent = filtered.length.toLocaleString('ko-KR');
      });
      if (!grid) return;
      grid.innerHTML = filtered.map((gugu, index) => `
        <a class="product-card" href="product-detail.html?id=${gugu.id}">
          <div class="product-card-img">
            ${renderMedia(gugu.image_url, gugu.product_name, getFallbackLabel(index))}
            <div class="badge ${progressPct(gugu) >= 80 ? 'badge-live' : 'badge-hot'}">${progressPct(gugu) >= 80 ? '마감임박' : '진행중'}</div>
          </div>
          <div class="product-card-body" style="padding:12px">
            <div class="pc-inf">
              <div class="pc-av" style="background:#e83e8c">${escapeHtml(getAvatarLetter(gugu.profiles))}</div>
              <span class="pc-inf-name">${escapeHtml(getDisplayName(gugu.profiles))}</span>
            </div>
            <div class="pc-name">${escapeHtml(gugu.product_name)}</div>
            <div class="pc-price-row">
              <span class="pc-orig">${formatKRW(gugu.original_price)}</span>
              <span class="pc-sale">${formatKRW(gugu.sale_price)}</span>
              <span class="pc-disc">-${getDiscountRate(gugu)}%</span>
            </div>
            <div class="pc-bar"><div class="pc-fill" style="width:${progressPct(gugu)}%"></div></div>
            <div class="pc-meta"><span>${Number(gugu.current_participants || 0).toLocaleString('ko-KR')}명</span><span>${escapeHtml(daysLeft(gugu.end_date))}</span></div>
          </div>
        </a>
      `).join('') || '<div style="grid-column:1/-1;text-align:center;color:var(--t2);padding:48px 0">이 카테고리에는 진행 중인 공구가 없어요.</div>';
    };

    tabs.forEach((tab) => {
      if (tab.textContent.trim() === currentCategory) tab.classList.add('active');
      tab.onclick = () => {
        tabs.forEach((item) => item.classList.remove('active'));
        tab.classList.add('active');
        currentCategory = tab.textContent.trim();
        render();
      };
    });

    render();
  }

  async function initSearchPage() {
    const gugus = await fetchActiveGugus();
    const params = new URLSearchParams(location.search);
    const input = document.getElementById('searchInput');
    const query = (params.get('q') || input?.value || '').trim();
    if (input) input.value = query;

    window.doSearch = function () {
      const next = input?.value?.trim() || '';
      location.href = next ? `search.html?q=${encodeURIComponent(next)}` : 'search.html';
    };

    const results = query
      ? gugus.filter((gugu) => {
          const haystack = [
            gugu.product_name,
            gugu.description,
            gugu.category,
            gugu.brand,
            getDisplayName(gugu.profiles)
          ].join(' ').toLowerCase();
          return haystack.includes(query.toLowerCase());
        })
      : gugus.slice(0, 12);

    const queryText = document.getElementById('queryText');
    if (queryText) queryText.textContent = query || '전체';
    const resultCount = document.getElementById('resultCount');
    if (resultCount) resultCount.textContent = results.length.toLocaleString('ko-KR');

    const grid = document.getElementById('productGrid');
    const empty = document.getElementById('emptySearch');
    if (!grid || !empty) return;

    if (!results.length) {
      grid.innerHTML = '';
      empty.style.display = 'flex';
      return;
    }

    empty.style.display = 'none';
    grid.innerHTML = results.map((gugu, index) => `
      <a class="product-card" href="product-detail.html?id=${gugu.id}">
        <div class="product-card-img">
          ${renderMedia(gugu.image_url, gugu.product_name, getFallbackLabel(index))}
          <div class="badge ${progressPct(gugu) >= 80 ? 'badge-live' : 'badge-end'}">${progressPct(gugu) >= 80 ? '마감임박' : '진행중'}</div>
        </div>
        <div class="product-card-body" style="padding:12px">
          <div class="pc-inf">
            <div class="pc-av" style="background:#e83e8c">${escapeHtml(getAvatarLetter(gugu.profiles))}</div>
            <span class="pc-inf-name">${escapeHtml(getDisplayName(gugu.profiles))}</span>
          </div>
          <div class="pc-name">${escapeHtml(gugu.product_name)}</div>
          <div class="pc-price-row">
            <span class="pc-orig">${formatKRW(gugu.original_price)}</span>
            <span class="pc-sale">${formatKRW(gugu.sale_price)}</span>
            <span class="pc-disc">-${getDiscountRate(gugu)}%</span>
          </div>
          <div class="pc-bar"><div class="pc-fill" style="width:${progressPct(gugu)}%"></div></div>
          <div class="pc-meta"><span>${Number(gugu.current_participants || 0).toLocaleString('ko-KR')}명</span><span>${escapeHtml(daysLeft(gugu.end_date))}</span></div>
        </div>
      </a>
    `).join('');
  }

  async function initProductDetailPage() {
    const params = new URLSearchParams(location.search);
    const guguId = params.get('id');
    if (!guguId) return;

    const { data: gugu } = await sb
      .from('gugus')
      .select('*, profiles!gugus_influencer_id_fkey(id, name, channel_name, follower_count)')
      .eq('id', guguId)
      .single();

    if (!gugu) return;

    window.currentGugu = gugu;
    if (typeof window.price !== 'undefined') window.price = Number(gugu.sale_price || 0);
    if (typeof window.changeQty === 'function') window.changeQty(0);

    document.title = `GUGU. ${gugu.product_name}`;
    const name = getDisplayName(gugu.profiles);
    if (q('.bc-cur')) q('.bc-cur').textContent = gugu.product_name;
    if (q('.pd-title')) q('.pd-title').textContent = gugu.product_name;
    if (q('.pd-orig')) q('.pd-orig').textContent = formatKRW(gugu.original_price);
    if (q('.pd-sale')) q('.pd-sale').textContent = formatKRW(gugu.sale_price);
    if (q('.pd-disc')) q('.pd-disc').textContent = `-${getDiscountRate(gugu)}%`;
    if (q('.pd-av')) q('.pd-av').textContent = getAvatarLetter(gugu.profiles);
    if (q('.pd-inf-name')) q('.pd-inf-name').textContent = name;
    if (q('.pd-inf-sub')) q('.pd-inf-sub').textContent = `${gugu.profiles?.follower_count ? `팔로워 ${Number(gugu.profiles.follower_count).toLocaleString('ko-KR')}명` : '인플루언서'} · ${gugu.category || '공구'}`;
    if (q('.pd-img-main')) q('.pd-img-main').innerHTML = renderMedia(gugu.image_url, gugu.product_name, 'IMG');
    if (q('.pd-prog-fill')) q('.pd-prog-fill').style.width = `${progressPct(gugu)}%`;
    if (q('.pd-prog-row')) q('.pd-prog-row').innerHTML = `<span>${Number(gugu.current_participants || 0).toLocaleString('ko-KR')}명 참여</span><span style="color:var(--r);font-weight:600">${escapeHtml(daysLeft(gugu.end_date))}</span>`;
    if (q('.pd-viewers')) q('.pd-viewers').innerHTML = `지금 <span>${Math.max(12, Math.round((gugu.current_participants || 0) / 5))}명</span>이 이 공구를 보고 있어요`;

    const desc = q('#tab-desc .prod-desc');
    if (desc) {
      desc.innerHTML = `
        <h4>상품 소개</h4>
        <p>${escapeHtml(gugu.description || '인플루언서가 직접 큐레이션한 공구 상품입니다.')}</p>
        <h4>상품 정보</h4>
        <div class="desc-list">
          <div class="dl-item"><div class="dl-dot"></div>카테고리: ${escapeHtml(gugu.category || '미정')}</div>
          <div class="dl-item"><div class="dl-dot"></div>브랜드: ${escapeHtml(gugu.brand || '브랜드 정보 준비중')}</div>
          <div class="dl-item"><div class="dl-dot"></div>최소 주문 수량: ${Number(gugu.min_per_person || 1)}개</div>
          <div class="dl-item"><div class="dl-dot"></div>최대 주문 수량: ${Number(gugu.max_per_person || 3)}개</div>
        </div>`;
    }

    const deliveryValues = qa('.pd-del-v');
    if (deliveryValues[0]) deliveryValues[0].textContent = gugu.shipping_days || '공구 마감 후 순차 발송';
    if (deliveryValues[1]) deliveryValues[1].textContent = Number(gugu.shipping_cost || 0) === 0 ? '무료배송' : formatKRW(gugu.shipping_cost);
    if (deliveryValues[2]) deliveryValues[2].textContent = gugu.return_policy || '수령 후 7일 이내';

    const { data: related } = await sb
      .from('gugus')
      .select('id, product_name, sale_price, original_price, image_url')
      .eq('influencer_id', gugu.influencer_id)
      .neq('id', gugu.id)
      .limit(4);

    const relatedGrid = q('.related-grid');
    if (relatedGrid) {
      relatedGrid.innerHTML = (related || []).map((item, index) => `
        <a class="rc" href="product-detail.html?id=${item.id}">
          <div class="rc-img">${renderMedia(item.image_url, item.product_name, getFallbackLabel(index))}</div>
          <div class="rc-body">
            <div class="rc-name">${escapeHtml(item.product_name)}</div>
            <div class="rc-price">${formatKRW(item.sale_price)} <span class="rc-disc">-${getDiscountRate(item)}%</span></div>
          </div>
        </a>
      `).join('');
    }

    window.doBuy = async function () {
      const btn = document.getElementById('buyBtn');
      const err = document.getElementById('buyErr');
      const ok = document.getElementById('buyOk');
      err.style.display = 'none';
      ok.style.display = 'none';

      const user = await getCurrentUser();
      if (!user) {
        err.style.display = 'block';
        err.innerHTML = '구매하려면 로그인이 필요해요. <a href="login.html" style="color:var(--r);font-weight:700">로그인하기</a>';
        return;
      }

      if (user.profile?.role === 'influencer') {
        err.style.display = 'block';
        err.textContent = '인플루언서 계정으로는 구매할 수 없어요.';
        return;
      }

      const qtyValue = parseInt(document.getElementById('qty')?.textContent || '1', 10) || 1;
      const totalAmount = Number(gugu.sale_price || 0) * qtyValue;
      btn.textContent = '주문 처리 중...';
      btn.disabled = true;

      const { error } = await sb.from('orders').insert({
        gugu_id: gugu.id,
        consumer_id: user.id,
        quantity: qtyValue,
        unit_price: Number(gugu.sale_price || 0),
        total_amount: totalAmount,
        status: 'paid'
      });

      if (error) {
        err.style.display = 'block';
        err.textContent = `주문 중 오류가 발생했어요: ${error.message}`;
        btn.textContent = '지금 공구 참여하기';
        btn.disabled = false;
        return;
      }

      await sb.rpc('increment_participants', { p_gugu_id: gugu.id });
      ok.style.display = 'block';
      ok.textContent = '공구 참여가 완료됐어요.';
      btn.textContent = '주문 완료!';
      btn.style.background = 'var(--g)';
      btn.disabled = false;
      setTimeout(() => { location.href = 'order-complete.html'; }, 1200);
    };
  }

  async function initInfluencerProfilePage() {
    const params = new URLSearchParams(location.search);
    const influencerId = params.get('id');
    if (!influencerId) return;

    const [{ data: profile }, { data: gugus }] = await Promise.all([
      sb.from('profiles').select('*').eq('id', influencerId).single(),
      sb.from('gugus').select('*').eq('influencer_id', influencerId).order('created_at', { ascending: false })
    ]);

    if (!profile) return;

    const active = (gugus || []).filter(isActiveGugu);
    const closed = (gugus || []).filter((gugu) => !isActiveGugu(gugu));
    const totalParticipants = (gugus || []).reduce((sum, gugu) => sum + Number(gugu.current_participants || 0), 0);
    const avgProgress = gugus?.length ? Math.round(gugus.reduce((sum, gugu) => sum + progressPct(gugu), 0) / gugus.length) : 0;

    document.title = `GUGU. ${getDisplayName(profile)} 프로필`;
    if (q('.profile-av')) q('.profile-av').textContent = getAvatarLetter(profile);
    if (q('.profile-name')) q('.profile-name').innerHTML = `${escapeHtml(getDisplayName(profile))} <div class="verified">✓</div>${active.length ? ' <span class="live-now"><span class="dot"></span> 공구 진행중</span>' : ''}`;
    if (q('.profile-handle')) q('.profile-handle').textContent = `${profile.channel_url || '@gugu_influencer'} · ${profile.channel_name || 'influencer'}`;

    const metaStats = qa('.meta-stat .n');
    if (metaStats[0]) metaStats[0].textContent = profile.follower_count ? Number(profile.follower_count).toLocaleString('ko-KR') : '-';
    if (metaStats[1]) metaStats[1].textContent = active.length.toLocaleString('ko-KR');
    if (metaStats[2]) metaStats[2].textContent = `${avgProgress}%`;
    if (metaStats[3]) metaStats[3].textContent = totalParticipants.toLocaleString('ko-KR');

    const tagWrap = q('.profile-tags');
    if (tagWrap) {
      const categories = [...new Set((gugus || []).map((gugu) => gugu.category).filter(Boolean))];
      tagWrap.innerHTML = categories.map((category) => `<span class="tag"># ${escapeHtml(category)}</span>`).join('') || '<span class="tag"># 공구</span>';
    }

    const sidebarStats = qa('.stat-item .n');
    if (sidebarStats[0]) sidebarStats[0].textContent = `${avgProgress}%`;
    if (sidebarStats[1]) sidebarStats[1].textContent = `${(gugus || []).length}개`;
    if (sidebarStats[2]) sidebarStats[2].textContent = `${active.length}개`;
    if (sidebarStats[3]) sidebarStats[3].textContent = `${totalParticipants.toLocaleString('ko-KR')}명`;

    const recentList = q('.recent-list');
    if (recentList) {
      recentList.innerHTML = closed.slice(0, 3).map((gugu, index) => `
        <div class="recent-item">
          <div class="recent-emoji">${renderMedia(gugu.image_url, gugu.product_name, getFallbackLabel(index), 'border-radius:6px')}</div>
          <div class="recent-info">
            <div class="name">${escapeHtml(gugu.product_name)}</div>
            <div class="price">${formatKRW(gugu.sale_price)} · ${Number(gugu.current_participants || 0).toLocaleString('ko-KR')}명 참여</div>
          </div>
        </div>
      `).join('') || '<div style="color:var(--t2);font-size:12px">종료된 공구가 아직 없어요.</div>';
    }

    const tabs = qa('.profile-tab');
    const grid = q('.pg-grid');
    if (!grid) return;
    const renderGrid = (list, closedMode) => {
      grid.innerHTML = list.map((gugu, index) => `
        <a class="pc" href="product-detail.html?id=${gugu.id}">
          <div class="pc-img">
            ${renderMedia(gugu.image_url, gugu.product_name, getFallbackLabel(index))}
            <div class="pc-badge ${closedMode ? 'done' : ''}">${closedMode ? '종료' : '진행중'}</div>
          </div>
          <div class="pc-body" style="padding:12px">
            <div class="pc-name">${escapeHtml(gugu.product_name)}</div>
            <div class="pc-price-row">
              <span class="pc-orig">${formatKRW(gugu.original_price)}</span>
              <span class="pc-sale">${formatKRW(gugu.sale_price)}</span>
              <span class="pc-disc">-${getDiscountRate(gugu)}%</span>
            </div>
            <div class="pc-bar"><div class="pc-fill" style="width:${closedMode ? 100 : progressPct(gugu)}%"></div></div>
            <div class="pc-meta"><span>${Number(gugu.current_participants || 0).toLocaleString('ko-KR')}명</span><span>${closedMode ? '종료' : escapeHtml(daysLeft(gugu.end_date))}</span></div>
          </div>
        </a>
      `).join('') || '<div style="grid-column:1/-1;color:var(--t2);padding:32px 0">표시할 공구가 없어요.</div>';
    };

    renderGrid(active, false);
    tabs.forEach((tab, index) => {
      tab.onclick = () => {
        tabs.forEach((item) => item.classList.remove('active'));
        tab.classList.add('active');
        if (index === 0) renderGrid(active, false);
        if (index === 1) renderGrid(closed, true);
        if (index === 2) grid.innerHTML = '<div style="grid-column:1/-1;color:var(--t2);padding:32px 0">후기 기능은 다음 단계에서 연결할 예정입니다.</div>';
      };
    });
  }
})();
