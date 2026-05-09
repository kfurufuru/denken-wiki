/**
 * chatgpt-prompt.js — 条文ページにChatGPT誘導ボックスを注入（3モード独立ボックス）
 *
 * 対象: URL に /articles/ を含むページ（kijun / kaishaku / jigyoho）
 * モード（各モード独立した <details> ボックスとして並ぶ。閉じたまま判別できる）:
 *   1) 🤖 ChatGPTに質問する          — 自由質問用
 *   2) 🔍 ChatGPTで公開前レビュー    — 4観点厳しめレビュー（優先度A/B/C・一括修正指示文まで生成）
 *   3) ✅ ChatGPTで修正版チェック    — Claude Code 修正後の再レビュー（簡易版）
 * 動作: .md-typeset の末尾に <div class="chatgpt-prompts"> を追加
 *       MkDocs Material の SPA ナビゲーション（document$）に対応
 */
(function () {
  'use strict';

  var SITE_NAME = '電験3種 法規Wiki';
  var CHATGPT_URL = 'https://chat.openai.com/';
  var CSS_VERSION = '20260509e'; // CSS変更時に bump → ブラウザCSSキャッシュ強制更新

  // ブラウザがcustom.cssを古いまま掴んでいる対策：
  // <link rel="stylesheet" href="...custom.css"> に ?v=CSS_VERSION を1度だけ付与して再フェッチ
  function bustCssCache() {
    var marker = '__chatgptPromptCssBusted_' + CSS_VERSION;
    if (window[marker]) return;
    window[marker] = true;
    document.querySelectorAll('link[rel="stylesheet"]').forEach(function (link) {
      if (!link.href || link.href.indexOf('custom.css') === -1) return;
      var base = link.href.split('?')[0];
      link.href = base + '?v=' + CSS_VERSION;
    });
  }
  bustCssCache();

  function isArticlePage() {
    return window.location.pathname.includes('/articles/');
  }

  function getPageTitle() {
    var h1 = document.querySelector('.md-typeset h1');
    if (!h1) return document.title;
    return h1.textContent.trim().replace(/\s*[¶#]\s*$/, '').trim();
  }

  // ─────────────────────────────────────
  // モード定義（各モード独立ボックス）
  // ─────────────────────────────────────
  var MODES = [
    {
      key: 'question',
      label: '🤖 質問する',
      hint: '記事内容について自由に質問する用途。質問文を末尾に追記して送信。',
      build: function (title, url) {
        return [
          '以下の記事を参照して、私の質問に答えてください。',
          '',
          '【サイト】' + SITE_NAME,
          '【記事タイトル】' + title,
          '【URL】' + url,
          '',
          '# 質問',
          '（ここに質問を書いてください）'
        ].join('\n');
      }
    },
    {
      key: 'review',
      label: '🔍 公開前レビュー',
      hint: '法令正確性・出題対策・初学者・UIの4観点で総合レビュー。優先度A/B/Cと Claude Code への一括修正指示文まで生成。',
      build: function (title, url) {
        return [
          '以下の記事を、電験3種・法規の学習ページとして公開前レビューしてください。',
          '',
          '【サイト】' + SITE_NAME,
          '【記事タイトル】' + title,
          '【URL】' + url,
          '',
          '# レビュー目的',
          '',
          'この記事が、電験3種・法規の受験者にとって、',
          '「正確に理解できる」',
          '「試験で得点につながる」',
          '「初学者でも迷わず読める」',
          '「UIとして見やすい」',
          'ページになっているかを厳しく確認してください。',
          '',
          '# レビュー観点',
          '',
          '## 1. 法令・制度の正確性',
          '- 法令・制度の説明に誤りがないか',
          '- 条文番号、数値条件、対象範囲、用語の使い方が正しいか',
          '- 「届出」「許可」「認可」「承認」「報告」「通知」などを混同していないか',
          '- 原則と例外が混ざっていないか',
          '- 経産省、e-Gov、産業保安監督部、試験センターなどの公的情報と矛盾していないか',
          '- 不明確な点は「要一次情報確認」と明記してください',
          '',
          '## 2. 電験3種・法規の出題対策',
          '- 電験3種で問われやすい論点が強調されているか',
          '- 数値・期限・対象範囲・行政手続きなどのひっかけに対応できているか',
          '- 受験者が覚えるべき優先順位が分かるか',
          '- 過去問や頻出論点とのつながりが分かるか',
          '- 試験に出にくい実務補足が前に出すぎていないか',
          '',
          '## 3. 初学者にとっての分かりやすさ',
          '- 冒頭で「このページで何を覚えるべきか」が分かるか',
          '- 専門用語の説明が不足していないか',
          '- 原則・例外・暗記ポイント・補足が分かれているか',
          '- 表や箇条書きが理解を助けているか',
          '- 情報量が多すぎて、逆に読みにくくなっていないか',
          '',
          '## 4. UI・見やすさ',
          '- 見出し構成は自然か',
          '- 表が長すぎないか',
          '- スマホでも読みやすいか',
          '- ボックス、表、強調表示の使い方が適切か',
          '- 重要度が視覚的に分かるか',
          '- 同じ内容の重複が多くないか',
          '- Claude Code修正による表現崩れ、構成崩れ、不自然な重複がないか',
          '',
          '## 5. 修正優先度',
          '改善点は以下の3段階で分類してください。',
          '',
          '- 優先度A：公開前に必ず直すべき点',
          '- 優先度B：直すとかなり良くなる点',
          '- 優先度C：余力があれば直す点',
          '',
          '# 出力形式',
          '',
          '以下の形式で回答してください。',
          '',
          '## 公開可否',
          '「このまま公開可」「軽微修正後に公開可」「要修正」のいずれかで判定してください。',
          '',
          '## 総合評価',
          '100点満点で評価し、理由を簡潔に説明してください。',
          '',
          '## 良い点',
          '正確性・出題対策・分かりやすさ・UIの観点で整理してください。',
          '',
          '## 問題点・改善点',
          '表形式で、以下の列で整理してください。',
          '',
          '| 優先度 | 問題点 | 理由 | 修正案 |',
          '|---|---|---|---|',
          '',
          '## 特に注意すべき誤解ポイント',
          '受験者が間違えやすい点、試験でひっかけられやすい点を整理してください。',
          '',
          '## UI改善案',
          '見出し、表、ボックス、導線、スマホ表示の観点で改善案を出してください。',
          '',
          '## Claude Codeへの一括修正指示文',
          '上記の改善点を反映するため、Claude Codeにそのまま貼り付けられる一括修正指示文を作成してください。'
        ].join('\n');
      }
    },
    {
      key: 'recheck',
      label: '✅ 修正版チェック',
      hint: 'Claude Code 修正後の再レビュー用（簡易版）。残課題の優先度A/B・追加修正指示文まで生成。',
      build: function (title, url) {
        return [
          '以下の記事は、Claude Codeで修正した後の版です。',
          '電験3種・法規の学習ページとして、公開前レビューをしてください。',
          '',
          '【サイト】' + SITE_NAME,
          '【記事タイトル】' + title,
          '【URL】' + url,
          '',
          '# 確認してほしいこと',
          '',
          '1. 修正によって法令・制度の誤りが入っていないか',
          '2. 条文番号、数値条件、対象範囲、用語が正しいか',
          '3. 電験3種の出題対策として有効か',
          '4. 初学者が迷わず読める構成か',
          '5. UIが見やすいか',
          '6. Claude Code修正による不自然な重複、表現崩れ、表の肥大化がないか',
          '7. 公開前に必ず直すべき点が残っていないか',
          '',
          '# 特に見る観点',
          '',
          '- 原則と例外が混ざっていないか',
          '- 「届出」「許可」「認可」「承認」「報告」「通知」などの行政手続きが混同されていないか',
          '- 数値条件や期限が正しいか',
          '- 試験で問われる内容と実務補足の優先順位が逆転していないか',
          '- 表やボックスが増えすぎて読みにくくなっていないか',
          '',
          '# 出力形式',
          '',
          '## 公開可否',
          '「このまま公開可」「軽微修正後に公開可」「要修正」で判定してください。',
          '',
          '## 総合評価',
          '100点満点で評価してください。',
          '',
          '## 必ず直すべき点',
          '優先度Aのみを表で整理してください。',
          '',
          '## 直すとさらに良くなる点',
          '優先度B・Cを表で整理してください。',
          '',
          '## UI・見やすさの評価',
          'スマホ表示、表の読みやすさ、見出し導線、ボックスの使い方を評価してください。',
          '',
          '## Claude Codeへの追加修正指示文',
          '必要な修正がある場合、Claude Codeにそのまま貼れる一括指示文を作成してください。'
        ].join('\n');
      }
    }
  ];

  // ─────────────────────────────────────
  // 単一ボックスを生成
  // ─────────────────────────────────────
  // モード別の左ボーダー色（CSS だけでは MkDocs Material のデフォルト
  // .md-typeset summary の background が打ち消せないため、インラインで強制）
  var MODE_ACCENT = {
    question: '#2E8B8E',
    review:   '#d97706',
    recheck:  '#16a34a'
  };

  function createSingleBox(mode, title, url) {
    var promptText = mode.build(title, url);

    var box = document.createElement('div');
    box.className = 'chatgpt-box chatgpt-box--' + mode.key;
    box.setAttribute('data-mode', mode.key);

    var details = document.createElement('details');
    details.className = 'chatgpt-box__details';

    var summary = document.createElement('summary');
    summary.className = 'chatgpt-box__summary';
    summary.textContent = mode.label;
    // インライン !important で MkDocs Material の details>summary 既定スタイルを確実に上書き
    summary.style.setProperty('background', '#ffffff', 'important');
    summary.style.setProperty('color', '#1f2937', 'important');
    summary.style.setProperty('border-left', '3px solid ' + (MODE_ACCENT[mode.key] || '#888'), 'important');
    summary.style.setProperty('padding', '0.55rem 1rem 0.55rem 0.85rem', 'important');
    summary.style.setProperty('font-weight', '600', 'important');
    summary.addEventListener('mouseenter', function () {
      summary.style.setProperty('background', '#f9fafb', 'important');
    });
    summary.addEventListener('mouseleave', function () {
      summary.style.setProperty('background', '#ffffff', 'important');
    });

    var body = document.createElement('div');
    body.className = 'chatgpt-box__body';

    var textarea = document.createElement('textarea');
    textarea.className = 'chatgpt-box__textarea';
    textarea.readOnly = true;
    textarea.rows = mode.key === 'question' ? 7 : 12;
    textarea.value = promptText;

    var hint = document.createElement('p');
    hint.className = 'chatgpt-box__hint';
    hint.textContent = mode.hint;

    var actions = document.createElement('div');
    actions.className = 'chatgpt-box__actions';

    var copyBtn = document.createElement('button');
    copyBtn.type = 'button';
    copyBtn.className = 'chatgpt-box__btn chatgpt-box__btn--copy';
    copyBtn.innerHTML = '📋 プロンプトをコピー';
    copyBtn.addEventListener('click', function () {
      var doneLabel = '✅ コピーしました';
      var origLabel = '📋 プロンプトをコピー';
      function flash() {
        copyBtn.textContent = doneLabel;
        setTimeout(function () { copyBtn.innerHTML = origLabel; }, 2000);
      }
      if (navigator.clipboard) {
        navigator.clipboard.writeText(textarea.value).then(flash).catch(function () {
          textarea.select(); document.execCommand('copy'); flash();
        });
      } else {
        textarea.select(); document.execCommand('copy'); flash();
      }
    });

    var openLink = document.createElement('a');
    openLink.className = 'chatgpt-box__btn chatgpt-box__btn--open';
    openLink.href = CHATGPT_URL;
    openLink.target = '_blank';
    openLink.rel = 'noopener noreferrer';
    openLink.textContent = '↗ ChatGPTを開く';

    actions.appendChild(copyBtn);
    actions.appendChild(openLink);

    body.appendChild(textarea);
    body.appendChild(hint);
    body.appendChild(actions);
    details.appendChild(summary);
    details.appendChild(body);
    box.appendChild(details);
    return box;
  }

  // ─────────────────────────────────────
  // 全モードのコンテナを生成
  // ─────────────────────────────────────
  function createPromptsContainer(title, url) {
    var container = document.createElement('div');
    container.className = 'chatgpt-prompts';

    var header = document.createElement('div');
    header.className = 'chatgpt-prompts__header';
    header.innerHTML = '<span class="chatgpt-prompts__header-icon">🤖</span><span class="chatgpt-prompts__header-text">この記事を ChatGPT で使う</span>';
    container.appendChild(header);

    MODES.forEach(function (mode) {
      container.appendChild(createSingleBox(mode, title, url));
    });

    return container;
  }

  // 旧バージョン（.chatgpt-prompts に含まれない単独 .chatgpt-box）を毎回除去
  function cleanupStale() {
    document.querySelectorAll('.chatgpt-box').forEach(function (box) {
      if (!box.closest('.chatgpt-prompts')) {
        box.remove();
      }
    });
  }

  function inject() {
    if (!isArticlePage()) return;

    cleanupStale();

    if (document.querySelector('.chatgpt-prompts')) return;

    var typeset = document.querySelector('article .md-typeset, .md-content .md-typeset');
    if (!typeset) return;

    var title = getPageTitle();
    var url = window.location.href;
    typeset.appendChild(createPromptsContainer(title, url));
  }

  if (typeof window.document$ !== 'undefined' && typeof window.document$.subscribe === 'function') {
    window.document$.subscribe(inject);
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', inject);
  } else {
    inject();
  }
})();
