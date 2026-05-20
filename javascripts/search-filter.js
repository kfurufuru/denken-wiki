/* search-filter.js — 検索結果セクション絞り込みチップ */
(function () {
  'use strict';

  const CATS = [
    { label: 'すべて',   pattern: null },
    { label: '電技基準', pattern: 'articles/kijun/' },
    { label: '解釈',     pattern: 'articles/kaishaku/' },
    { label: '電事法',   pattern: 'articles/jigyoho/' },
    { label: '他法令',   pattern: 'articles/other/' },
    { label: 'テーマ別', pattern: 'themes/' },
    { label: '過去問',   pattern: 'kakomon/' },
    { label: '理論',     pattern: 'theory/' },
  ];

  let activePattern = null;

  function applyFilter(resultEl) {
    const list = resultEl.querySelector('.md-search-result__list');
    if (!list) return;
    const items = [...list.querySelectorAll(':scope > li')];
    if (!items.length) return;

    let visible = 0;
    items.forEach(li => {
      const a = li.querySelector('a[href]');
      const href = a ? a.getAttribute('href') : '';
      const show = !activePattern || href.includes(activePattern);
      li.hidden = !show;
      if (show) visible++;
    });

    if (activePattern !== null) {
      const meta = resultEl.querySelector('.md-search-result__meta');
      const cat = CATS.find(c => c.pattern === activePattern);
      if (meta && cat) {
        const next = `「${cat.label}」で絞り込み中`;
        if (meta.textContent !== next) meta.textContent = next;
      }
    }
  }

  function ensureBar(resultEl) {
    if (resultEl.querySelector('.sf-bar')) return;
    const list = resultEl.querySelector('.md-search-result__list');
    if (!list) return;

    const bar = document.createElement('div');
    bar.className = 'sf-bar';
    bar.setAttribute('role', 'group');
    bar.setAttribute('aria-label', 'セクションで絞り込み');

    CATS.forEach(({ label, pattern }) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'sf-chip' + (pattern === activePattern ? ' sf-chip--on' : '');
      btn.textContent = label;
      btn.addEventListener('click', () => {
        activePattern = pattern;
        bar.querySelectorAll('.sf-chip').forEach(c => c.classList.remove('sf-chip--on'));
        btn.classList.add('sf-chip--on');
        applyFilter(resultEl);
      });
      bar.appendChild(btn);
    });

    resultEl.insertBefore(bar, list);
  }

  document.addEventListener('DOMContentLoaded', () => {
    const resultEl = document.querySelector('[data-md-component="search-result"]');
    if (!resultEl) return;

    new MutationObserver(() => {
      ensureBar(resultEl);
      applyFilter(resultEl);
    }).observe(resultEl, { childList: true, subtree: true });
  });
})();
