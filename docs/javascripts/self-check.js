/**
 * セルフチェック・穴埋め過去問の理解度ボタン
 *
 * 対象:
 *   - <details class="question"> でサマリ先頭が「セルフチェック」
 *   - <div class="admonition abstract"> でタイトルが「問題」を含む
 *
 * localStorage 共有:
 *   キー: denken_check::<articleSlug>::<itemHash>
 *   値:   JSON { status, updatedAt, articleUrl, articleTitle, itemTitle, itemType }
 *
 * status: "understood" | "vague" | "review" | "wrong"
 */
(function () {
  'use strict';

  const STORAGE_PREFIX = 'denken_check::';

  const STATUSES = [
    { key: 'understood', label: '理解した', color: '#22c55e', icon: '✓' },
    { key: 'vague',      label: 'うる覚え', color: '#f59e0b', icon: '?' },
    { key: 'review',     label: '要確認',   color: '#f97316', icon: '!' },
    { key: 'wrong',      label: '間違えた', color: '#dc2626', icon: '✗' }
  ];

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

  function applyStatusClass(rootEl, status) {
    if (!rootEl) return;
    STATUSES.forEach(function (s) { rootEl.classList.remove('sc-status-' + s.key); });
    if (status) rootEl.classList.add('sc-status-' + status);
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
    applyStatusClass(rootEl, currentStatus);

    STATUSES.forEach(function (s) {
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
          clearStored(itemHash);
          updateTimestamp(wrap, null);
          applyStatusClass(rootEl, null);
        } else {
          btn.classList.add('active');
          const payload = {
            status: s.key,
            updatedAt: new Date().toISOString(),
            articleUrl: location.origin + location.pathname + location.hash,
            articleTitle: articleTitle(),
            itemTitle: itemTitle.slice(0, 200),
            itemType: itemType
          };
          setStored(itemHash, payload);
          updateTimestamp(wrap, payload.updatedAt);
          applyStatusClass(rootEl, s.key);
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
    });
  }

  function setup() {
    try {
      attachToSelfChecks();
      attachToKakomon();
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
