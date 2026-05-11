/**
 * 復習ノート — localStorage に記録された理解度ボタンを集約表示
 *
 * 対象:
 *   - キー形式: denken_check::<articleSlug>::<itemHash>
 *   - 値: JSON { status, updatedAt, articleUrl, articleTitle, itemTitle, itemType, memo }
 *
 * 表示:
 *   - フィルタ：すべて / 間違えた / 要確認 / うる覚え / 理解した
 *   - デフォルト：間違えた + 要確認 + うる覚え（復習が必要なもの）
 *   - ソート：更新日時降順
 *   - 各カード：状態バッジ・記事タイトル・問題タイトル・更新時刻・メモ・遷移リンク・個別削除
 *   - 一括クリア（フィルタ中のもののみ）
 */
(function () {
  'use strict';

  const STORAGE_PREFIX = 'denken_check::';

  const STATUS_DEFS = {
    understood: { label: '理解した', color: '#22c55e', icon: '✓' },
    vague:      { label: 'うる覚え', color: '#f59e0b', icon: '?' },
    review:     { label: '要確認',   color: '#f97316', icon: '!' },
    wrong:      { label: '間違えた', color: '#dc2626', icon: '✗' },
  };

  // 復習優先度（数値が小さいほど優先）
  const PRIORITY = { wrong: 0, review: 1, vague: 2, understood: 3 };

  function collectRecords() {
    const records = [];
    try {
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (!key || !key.startsWith(STORAGE_PREFIX)) continue;
        try {
          const raw = localStorage.getItem(key);
          if (!raw) continue;
          const parsed = JSON.parse(raw);
          if (!parsed || !parsed.status) continue; // status null は除外（memoのみ等）
          records.push({
            key,
            status: parsed.status,
            updatedAt: parsed.updatedAt || '',
            articleUrl: parsed.articleUrl || '',
            articleTitle: parsed.articleTitle || '(無題)',
            itemTitle: parsed.itemTitle || '(無題項目)',
            itemType: parsed.itemType || 'unknown',
            memo: parsed.memo || '',
          });
        } catch (e) { /* skip broken entry */ }
      }
    } catch (e) {
      console.warn('[review-notebook] localStorage scan failed', e);
    }
    return records;
  }

  function formatTs(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    if (isNaN(d.getTime())) return '';
    const y  = d.getFullYear();
    const m  = String(d.getMonth() + 1).padStart(2, '0');
    const dy = String(d.getDate()).padStart(2, '0');
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    return `${y}-${m}-${dy} ${hh}:${mm}`;
  }

  function el(tag, attrs, children) {
    const e = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(k => {
        if (k === 'style' && typeof attrs[k] === 'object') {
          Object.assign(e.style, attrs[k]);
        } else if (k === 'onclick') {
          e.addEventListener('click', attrs[k]);
        } else if (k.startsWith('data-')) {
          e.setAttribute(k, attrs[k]);
        } else {
          e[k] = attrs[k];
        }
      });
    }
    if (children) {
      (Array.isArray(children) ? children : [children]).forEach(c => {
        if (c == null) return;
        e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
      });
    }
    return e;
  }

  const STYLE = `
    .rn-toolbar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 16px; }
    .rn-filter-btn {
      padding: 4px 12px; border-radius: 999px; border: 1.5px solid var(--md-default-fg-color--lighter);
      background: transparent; color: var(--md-default-fg-color); cursor: pointer;
      font-size: 12px; font-weight: 700; font-family: inherit; display: inline-flex; align-items: center; gap: 4px;
      transition: all 0.15s;
    }
    .rn-filter-btn.active { color: #fff; }
    .rn-filter-btn .rn-count { font-size: 11px; opacity: 0.8; margin-left: 2px; }
    .rn-stats { font-size: 12px; color: var(--md-default-fg-color--light); margin-left: auto; }
    .rn-card {
      border: 1px solid var(--md-default-fg-color--lightest); border-left-width: 4px;
      border-radius: 6px; padding: 12px 16px; margin-bottom: 10px;
      background: var(--md-default-bg-color);
    }
    .rn-card-header { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 6px; }
    .rn-badge {
      display: inline-flex; align-items: center; gap: 3px;
      padding: 2px 10px; border-radius: 999px; font-size: 11px; font-weight: 700; color: #fff;
      letter-spacing: 0.02em; line-height: 1.5;
    }
    .rn-article-link { font-size: 13px; font-weight: 700; color: var(--md-primary-fg-color); text-decoration: none; }
    .rn-article-link:hover { text-decoration: underline; }
    .rn-item-title { font-size: 13px; color: var(--md-default-fg-color); margin-top: 2px; line-height: 1.55; }
    .rn-meta { font-size: 11px; color: var(--md-default-fg-color--light); margin-top: 6px; display: flex; gap: 12px; align-items: center; }
    .rn-meta-ts { font-variant-numeric: tabular-nums; }
    .rn-meta-type { padding: 1px 6px; border-radius: 3px; background: var(--md-code-bg-color); font-size: 10px; }
    .rn-memo { font-size: 12px; margin-top: 8px; padding: 6px 10px; border-left: 2px solid var(--md-default-fg-color--lighter); background: var(--md-code-bg-color); white-space: pre-wrap; }
    .rn-delete { margin-left: auto; padding: 2px 8px; border: 1px solid var(--md-default-fg-color--lighter); border-radius: 4px; background: transparent; cursor: pointer; font-size: 11px; color: var(--md-default-fg-color--light); font-family: inherit; }
    .rn-delete:hover { color: #dc2626; border-color: #dc2626; }
    .rn-empty { padding: 32px 16px; text-align: center; color: var(--md-default-fg-color--light); font-size: 13px; border: 1px dashed var(--md-default-fg-color--lighter); border-radius: 8px; }
    .rn-clear-all { margin-left: 8px; padding: 4px 12px; border: 1px solid var(--md-default-fg-color--lighter); border-radius: 999px; background: transparent; cursor: pointer; font-size: 12px; color: var(--md-default-fg-color--light); font-family: inherit; }
    .rn-clear-all:hover { color: #dc2626; border-color: #dc2626; }
  `;

  function injectStyle() {
    if (document.getElementById('rn-style')) return;
    const s = document.createElement('style');
    s.id = 'rn-style';
    s.textContent = STYLE;
    document.head.appendChild(s);
  }

  // フィルタ状態（クロージャ管理）
  // 'priority' = wrong + review + vague (デフォルト)
  // 'all', 'wrong', 'review', 'vague', 'understood' から選択
  let currentFilter = 'priority';

  function statusMatches(status, filter) {
    if (filter === 'all') return true;
    if (filter === 'priority') return status === 'wrong' || status === 'review' || status === 'vague';
    return status === filter;
  }

  function render(root) {
    const all = collectRecords();
    // 状態別カウント
    const counts = { wrong: 0, review: 0, vague: 0, understood: 0 };
    all.forEach(r => { if (counts[r.status] != null) counts[r.status]++; });

    // フィルタ適用
    const filtered = all.filter(r => statusMatches(r.status, currentFilter));
    // ソート：優先度 → 更新日時降順
    filtered.sort((a, b) => {
      const p = (PRIORITY[a.status] ?? 9) - (PRIORITY[b.status] ?? 9);
      if (p !== 0) return p;
      return (b.updatedAt || '').localeCompare(a.updatedAt || '');
    });

    root.innerHTML = '';

    // ツールバー
    const tools = el('div', { className: 'rn-toolbar' });
    const filters = [
      { key: 'priority',   label: '要復習',   color: '#dc2626', count: counts.wrong + counts.review + counts.vague },
      { key: 'wrong',      label: '間違えた', color: STATUS_DEFS.wrong.color,      count: counts.wrong },
      { key: 'review',     label: '要確認',   color: STATUS_DEFS.review.color,     count: counts.review },
      { key: 'vague',      label: 'うる覚え', color: STATUS_DEFS.vague.color,      count: counts.vague },
      { key: 'understood', label: '理解した', color: STATUS_DEFS.understood.color, count: counts.understood },
      { key: 'all',        label: 'すべて',   color: 'var(--md-primary-fg-color)', count: all.length },
    ];

    filters.forEach(f => {
      const active = currentFilter === f.key;
      const btn = el('button', {
        className: 'rn-filter-btn' + (active ? ' active' : ''),
        style: {
          borderColor: f.color,
          color: active ? '#fff' : f.color,
          background: active ? f.color : 'transparent',
        },
        onclick: () => { currentFilter = f.key; render(root); },
      }, [
        f.label,
        el('span', { className: 'rn-count' }, '(' + f.count + ')'),
      ]);
      tools.appendChild(btn);
    });

    const stats = el('div', { className: 'rn-stats' },
      '合計 ' + all.length + ' 件 / 表示 ' + filtered.length + ' 件');
    tools.appendChild(stats);

    if (filtered.length > 0) {
      const clearBtn = el('button', {
        className: 'rn-clear-all',
        onclick: () => {
          if (!confirm('現在表示中の ' + filtered.length + ' 件の理解度記録を削除しますか？\nメモは保持されます。')) return;
          filtered.forEach(r => {
            try { localStorage.removeItem(r.key); } catch (e) {}
          });
          render(root);
        },
      }, '表示中をクリア');
      tools.appendChild(clearBtn);
    }
    root.appendChild(tools);

    // 一覧
    if (filtered.length === 0) {
      const empty = el('div', { className: 'rn-empty' },
        currentFilter === 'priority'
          ? '🎉 復習が必要な項目はありません。各記事で理解度ボタンを押すとここに表示されます。'
          : '該当する記録がありません。');
      root.appendChild(empty);
      return;
    }

    filtered.forEach(r => {
      const def = STATUS_DEFS[r.status] || { label: r.status, color: '#999', icon: '?' };

      const badge = el('span', {
        className: 'rn-badge',
        style: { background: def.color },
      }, def.icon + ' ' + def.label);

      const articleLink = r.articleUrl
        ? el('a', { className: 'rn-article-link', href: r.articleUrl }, r.articleTitle)
        : el('span', { className: 'rn-article-link' }, r.articleTitle);

      const typeBadge = el('span', { className: 'rn-meta-type' }, r.itemType);
      const ts = el('span', { className: 'rn-meta-ts' }, formatTs(r.updatedAt));

      const deleteBtn = el('button', {
        className: 'rn-delete',
        onclick: () => {
          if (!confirm('この記録を削除しますか？')) return;
          try { localStorage.removeItem(r.key); } catch (e) {}
          render(root);
        },
      }, '削除');

      const header = el('div', { className: 'rn-card-header' }, [badge, articleLink]);
      const itemTitle = el('div', { className: 'rn-item-title' }, r.itemTitle);
      const meta = el('div', { className: 'rn-meta' }, [typeBadge, ts, deleteBtn]);

      const card = el('div', {
        className: 'rn-card',
        style: { borderLeftColor: def.color },
      }, [header, itemTitle, meta]);

      if (r.memo) {
        const memoEl = el('div', { className: 'rn-memo' }, '📝 ' + r.memo);
        card.appendChild(memoEl);
      }

      root.appendChild(card);
    });
  }

  function init() {
    const root = document.getElementById('review-notebook-root');
    if (!root) return;
    injectStyle();
    render(root);

    // localStorage 変更（他タブ更新）に追従
    window.addEventListener('storage', (ev) => {
      if (!ev.key || ev.key.startsWith(STORAGE_PREFIX)) render(root);
    });
  }

  if (typeof window.document$ !== 'undefined' && typeof window.document$.subscribe === 'function') {
    window.document$.subscribe(init);
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
