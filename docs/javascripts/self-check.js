/**
 * セルフチェック・穴埋め過去問の理解度ボタン
 *
 * 対象:
 *   - <details class="question"> でサマリ先頭が「セルフチェック」
 *   - <div class="admonition abstract"> でタイトルが「問題」を含む
 *
 * localStorage 共有:
 *   キー: denken_check::<articleSlug>::<itemHash>
 *   値:   JSON { status, updatedAt, articleUrl, articleTitle, itemTitle, itemType, memo }
 *
 * status: "understood" | "vague" | "review" | "wrong"
 *   - selfcheck (4ボタン): understood / vague / review / wrong
 *   - kakomon  (3ボタン): understood / vague / wrong  ※ 既存 'review' は vague として表示
 *
 * memo: kakomon ブロックのみ。textarea 入力を debounce で保存（status と独立）。
 */
(function () {
  'use strict';

  const STORAGE_PREFIX = 'denken_check::';

  const STATUSES_SELFCHECK = [
    { key: 'understood', label: '理解した', color: '#22c55e', icon: '✓' },
    { key: 'vague',      label: 'うる覚え', color: '#f59e0b', icon: '?' },
    { key: 'review',     label: '要確認',   color: '#f97316', icon: '!' },
    { key: 'wrong',      label: '間違えた', color: '#dc2626', icon: '✗' }
  ];

  const STATUSES_KAKOMON = [
    { key: 'understood', label: '理解した', color: '#22c55e', icon: '〇' },
    { key: 'vague',      label: '曖昧',     color: '#f59e0b', icon: '△' },
    { key: 'wrong',      label: '間違えた', color: '#dc2626', icon: '×' }
  ];

  // バッジ表示用に全 status key を網羅した配列（class 削除や検索用）
  const ALL_STATUSES = [
    { key: 'understood', label: '理解した', color: '#22c55e', icon: '✓' },
    { key: 'vague',      label: '曖昧',     color: '#f59e0b', icon: '?' },
    { key: 'review',     label: '要確認',   color: '#f97316', icon: '!' },
    { key: 'wrong',      label: '間違えた', color: '#dc2626', icon: '✗' }
  ];

  function statusesFor(itemType) {
    return itemType === 'kakomon' ? STATUSES_KAKOMON : STATUSES_SELFCHECK;
  }

  function djb2Hash(str) {
    let hash = 5381;
    for (let i = 0; i < str.length; i++) {
      hash = ((hash << 5) + hash) + str.charCodeAt(i);
      hash = hash & 0xffffffff;
    }
    return (hash >>> 0).toString(36);
  }

  function articleSlug() {
    let p = location.pathname.replace(/\/index\.html?$/, '/').replace(/\.html?$/, '');
    p = p.replace(/^\/+|\/+$/g, '');
    return p || 'index';
  }

  function articleTitle() {
    const h1 = document.querySelector('article h1, main h1, h1');
    return h1 ? h1.textContent.trim().slice(0, 120) : document.title;
  }

  function getStored(itemHash) {
    try {
      const raw = localStorage.getItem(STORAGE_PREFIX + articleSlug() + '::' + itemHash);
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      return null;
    }
  }

  function setStored(itemHash, payload) {
    try {
      localStorage.setItem(STORAGE_PREFIX + articleSlug() + '::' + itemHash, JSON.stringify(payload));
    } catch (e) { /* quota etc */ }
  }

  function clearStored(itemHash) {
    try {
      localStorage.removeItem(STORAGE_PREFIX + articleSlug() + '::' + itemHash);
    } catch (e) { /* */ }
  }

  // ボタンを取り消した時、memo は残す
  function clearStatusOnly(itemHash) {
    try {
      const cur = getStored(itemHash);
      if (cur && cur.memo) {
        cur.status = null;
        cur.updatedAt = new Date().toISOString();
        setStored(itemHash, cur);
      } else {
        localStorage.removeItem(STORAGE_PREFIX + articleSlug() + '::' + itemHash);
      }
    } catch (e) { /* */ }
  }

  function applyStatusClass(rootEl, status, itemType) {
    if (!rootEl) return;
    ALL_STATUSES.forEach(function (s) { rootEl.classList.remove('sc-status-' + s.key); });
    const existingBadge = rootEl.querySelector(':scope > summary > .sc-summary-badge, :scope > .admonition-title > .sc-summary-badge, :scope > p.admonition-title > .sc-summary-badge');
    if (existingBadge) existingBadge.remove();
    if (!status) return;

    // kakomon なのに review 状態だった場合は vague として表示（後方互換）
    let displayStatus = status;
    if (itemType === 'kakomon' && status === 'review') displayStatus = 'vague';

    rootEl.classList.add('sc-status-' + displayStatus);
    const titleEl = rootEl.matches('details')
      ? rootEl.querySelector(':scope > summary')
      : rootEl.querySelector(':scope > .admonition-title, :scope > p.admonition-title');
    if (!titleEl) return;
    const def = ALL_STATUSES.find(function (s) { return s.key === displayStatus; });
    if (!def) return;
    const badge = document.createElement('span');
    badge.className = 'sc-summary-badge sc-summary-badge-' + displayStatus;
    badge.textContent = def.icon + ' ' + def.label;
    titleEl.appendChild(badge);
  }

  function buildButtons(itemHash, itemTitle, itemType, rootEl) {
    const wrap = document.createElement('div');
    wrap.className = 'self-check-buttons';
    wrap.setAttribute('data-item-hash', itemHash);

    const label = document.createElement('span');
    label.className = 'self-check-label';
    label.textContent = '理解度:';
    wrap.appendChild(label);

    const stored = getStored(itemHash);
    const currentStatus = stored ? stored.status : null;
    applyStatusClass(rootEl, currentStatus, itemType);

    const statuses = statusesFor(itemType);

    statuses.forEach(function (s) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'self-check-btn';
      btn.setAttribute('data-status', s.key);
      btn.style.setProperty('--btn-color', s.color);
      btn.innerHTML = '<span class="sc-icon">' + s.icon + '</span><span class="sc-label">' + s.label + '</span>';
      if (currentStatus === s.key) btn.classList.add('active');

      btn.addEventListener('click', function () {
        const wasActive = btn.classList.contains('active');
        wrap.querySelectorAll('.self-check-btn').forEach(function (b) { b.classList.remove('active'); });
        if (wasActive) {
          clearStatusOnly(itemHash);
          updateTimestamp(wrap, null);
          applyStatusClass(rootEl, null, itemType);
        } else {
          btn.classList.add('active');
          const existing = getStored(itemHash) || {};
          const payload = {
            status: s.key,
            updatedAt: new Date().toISOString(),
            articleUrl: location.origin + location.pathname + location.hash,
            articleTitle: articleTitle(),
            itemTitle: itemTitle.slice(0, 200),
            itemType: itemType,
            memo: existing.memo || ''
          };
          setStored(itemHash, payload);
          updateTimestamp(wrap, payload.updatedAt);
          applyStatusClass(rootEl, s.key, itemType);
        }
      });

      wrap.appendChild(btn);
    });

    const ts = document.createElement('span');
    ts.className = 'self-check-ts';
    wrap.appendChild(ts);
    if (stored && stored.updatedAt) updateTimestamp(wrap, stored.updatedAt);

    return wrap;
  }

  function buildMemo(itemHash, rootEl) {
    const memoWrap = document.createElement('div');
    memoWrap.className = 'self-check-memo';
    memoWrap.setAttribute('data-item-hash', itemHash);

    const textarea = document.createElement('textarea');
    textarea.className = 'self-check-memo-input';
    textarea.rows = 2;
    textarea.placeholder = 'メモ：気付き・間違えた理由・暗記補助など';

    // 既存メモを取得
    const stored = getStored(itemHash);
    if (stored && stored.memo) {
      textarea.value = stored.memo;
    }

    // 入力変化を debounce で保存（500ms）
    let timer = null;
    textarea.addEventListener('input', function () {
      clearTimeout(timer);
      timer = setTimeout(function () {
        const cur = getStored(itemHash) || {
          status: null,
          articleUrl: location.origin + location.pathname + location.hash,
          articleTitle: articleTitle(),
          itemTitle: '',
          itemType: 'kakomon'
        };
        cur.memo = textarea.value;
        cur.updatedAt = new Date().toISOString();
        setStored(itemHash, cur);
      }, 500);
    });

    memoWrap.appendChild(textarea);
    return memoWrap;
  }

  function updateTimestamp(wrap, iso) {
    const ts = wrap.querySelector('.self-check-ts');
    if (!ts) return;
    if (!iso) {
      ts.textContent = '';
      return;
    }
    const d = new Date(iso);
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    ts.textContent = '記録: ' + (d.getFullYear()) + '-' + m + '-' + day + ' ' + hh + ':' + mm;
  }

  function attachToSelfChecks() {
    // セルフチェック (??? question) — pymdownx.details renders <details class="question">
    const details = document.querySelectorAll('details.question, details.セルフチェック');
    details.forEach(function (el) {
      if (el.querySelector(':scope > .self-check-buttons')) return;
      const summary = el.querySelector('summary');
      if (!summary) return;
      const summaryText = summary.textContent.trim();
      if (!/セルフチェック/.test(summaryText)) return;

      const hash = djb2Hash('selfcheck::' + summaryText);
      const buttons = buildButtons(hash, summaryText, 'selfcheck', el);
      el.appendChild(buttons);
    });
  }

  function attachToKakomon() {
    // 穴埋め過去問チャレンジ (!!! abstract "問題N: ...") — Material renders <div class="admonition abstract">
    const blocks = document.querySelectorAll('div.admonition.abstract');
    blocks.forEach(function (el) {
      if (el.querySelector(':scope > .self-check-buttons')) return;
      const titleEl = el.querySelector(':scope > .admonition-title, :scope > p.admonition-title');
      if (!titleEl) return;
      const titleText = titleEl.textContent.trim();
      if (!/問題/.test(titleText)) return;

      const hash = djb2Hash('kakomon::' + titleText);
      const buttons = buildButtons(hash, titleText, 'kakomon', el);
      el.appendChild(buttons);
      const memo = buildMemo(hash, el);
      el.appendChild(memo);
    });
  }

  function attachToKakomonExamples() {
    // 過去問演習 (??? example "R0X/H2X 問N ...") — pymdownx.details renders <details class="example">
    // タイトルに「R\d+」「H\d+」「問\d+」を含むものを kakomon として扱う
    const details = document.querySelectorAll('details.example');
    details.forEach(function (el) {
      if (el.querySelector(':scope > .self-check-buttons')) return;
      const summary = el.querySelector('summary');
      if (!summary) return;
      const summaryText = summary.textContent.trim();
      // 過去問らしき形式：年度表記（R0X、H2X、令和、平成）+問番号、または「過去問」を含む
      if (!/(R\d+|H\d+|令和|平成|過去問).*問/.test(summaryText)) return;

      const hash = djb2Hash('kakomon-example::' + summaryText);
      const buttons = buildButtons(hash, summaryText, 'kakomon', el);
      el.appendChild(buttons);
      const memo = buildMemo(hash, el);
      el.appendChild(memo);
    });
  }

  function setup() {
    try {
      attachToSelfChecks();
      attachToKakomon();
      attachToKakomonExamples();
    } catch (e) {
      console.warn('[self-check] setup failed:', e);
    }
  }

  if (typeof window.document$ !== 'undefined' && typeof window.document$.subscribe === 'function') {
    window.document$.subscribe(setup);
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setup);
  } else {
    setup();
  }
})();
