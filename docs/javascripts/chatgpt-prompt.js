/**
 * chatgpt-prompt.js — 条文ページにChatGPT誘導ボックスを注入
 *
 * 対象: URL に /articles/ を含むページ（kijun / kaishaku / jigyoho）
 * 動作: .md-typeset の末尾に <div class="chatgpt-box"> を追加
 *       MkDocs Material の SPA ナビゲーション（document$）に対応
 */
(function () {
  'use strict';

  var SITE_NAME = '電験3種 法規Wiki';
  var CHATGPT_URL = 'https://chat.openai.com/';

  function isArticlePage() {
    return window.location.pathname.includes('/articles/');
  }

  function getPageTitle() {
    var h1 = document.querySelector('.md-typeset h1');
    if (!h1) return document.title;
    // MkDocs Material のパーマリンク記号（¶）を除去
    return h1.textContent.trim().replace(/\s*[¶#]\s*$/, '').trim();
  }

  function buildPromptText(title, url) {
    return (
      '以下の記事を参照して、私の質問に答えてください。\n\n' +
      '【サイト】' + SITE_NAME + '\n' +
      '【記事タイトル】' + title + '\n' +
      '【URL】' + url + '\n\n' +
      '# 質問\n（ここに質問を書いてください）'
    );
  }

  function createBox(title, url) {
    var promptText = buildPromptText(title, url);

    var box = document.createElement('div');
    box.className = 'chatgpt-box';

    var details = document.createElement('details');
    details.className = 'chatgpt-box__details';

    var summary = document.createElement('summary');
    summary.className = 'chatgpt-box__summary';
    summary.innerHTML = '<span class="chatgpt-box__icon">🤖</span> この記事をChatGPTに渡す（プロンプト生成）';

    var body = document.createElement('div');
    body.className = 'chatgpt-box__body';

    var textarea = document.createElement('textarea');
    textarea.className = 'chatgpt-box__textarea';
    textarea.readOnly = true;
    textarea.rows = 7;
    textarea.value = promptText;

    var actions = document.createElement('div');
    actions.className = 'chatgpt-box__actions';

    var copyBtn = document.createElement('button');
    copyBtn.className = 'chatgpt-box__btn chatgpt-box__btn--copy';
    copyBtn.innerHTML = '📋 プロンプトをコピー';
    copyBtn.addEventListener('click', function () {
      if (navigator.clipboard) {
        navigator.clipboard.writeText(textarea.value).then(function () {
          copyBtn.textContent = '✅ コピーしました';
          setTimeout(function () { copyBtn.innerHTML = '📋 プロンプトをコピー'; }, 2000);
        });
      } else {
        textarea.select();
        document.execCommand('copy');
        copyBtn.textContent = '✅ コピーしました';
        setTimeout(function () { copyBtn.innerHTML = '📋 プロンプトをコピー'; }, 2000);
      }
    });

    var openLink = document.createElement('a');
    openLink.className = 'chatgpt-box__btn chatgpt-box__btn--open';
    openLink.href = CHATGPT_URL;
    openLink.target = '_blank';
    openLink.rel = 'noopener noreferrer';
    openLink.textContent = '↗ ChatGPTを開く';

    var hint = document.createElement('p');
    hint.className = 'chatgpt-box__hint';
    hint.textContent = '使い方: コピー → ChatGPT で貼り付け → 質問を追記して送信。';

    actions.appendChild(copyBtn);
    actions.appendChild(openLink);
    body.appendChild(textarea);
    body.appendChild(actions);
    body.appendChild(hint);
    details.appendChild(summary);
    details.appendChild(body);
    box.appendChild(details);
    return box;
  }

  function inject() {
    if (!isArticlePage()) return;

    // 多重挿入防止
    if (document.querySelector('.chatgpt-box')) return;

    var typeset = document.querySelector('article .md-typeset, .md-content .md-typeset');
    if (!typeset) return;

    var title = getPageTitle();
    var url = window.location.href;

    typeset.appendChild(createBox(title, url));
  }

  // MkDocs Material SPA ナビゲーション対応
  if (typeof window.document$ !== 'undefined' && typeof window.document$.subscribe === 'function') {
    window.document$.subscribe(inject);
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', inject);
  } else {
    inject();
  }
})();
