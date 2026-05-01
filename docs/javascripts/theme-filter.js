document.addEventListener('DOMContentLoaded', function () {
  var input = document.getElementById('theme-search-input');
  if (!input) return;
  input.addEventListener('input', function () {
    var q = input.value.toLowerCase();
    document.querySelectorAll('#theme-grid .theme-card').forEach(function (card) {
      card.style.display = card.textContent.toLowerCase().includes(q) ? '' : 'none';
    });
  });
});