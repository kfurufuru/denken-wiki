window.MathJax = {
  tex: {
    inlineMath: [["\\(", "\\)"]],
    displayMath: [["\\[", "\\]"]],
    processEscapes: true,
    processEnvironments: true
  },
  options: {
    ignoreHtmlClass: ".*|",
    processHtmlClass: "arithmatex"
  }
};

document$.subscribe(() => {
  if (window.MathJax && window.MathJax.typesetPromise) {
    window.MathJax.startup.output.clearCache();
    window.MathJax.typesetClear();
    window.MathJax.texReset();
    window.MathJax.typesetPromise();
  }
});
