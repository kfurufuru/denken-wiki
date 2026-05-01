(function () {
  function setupTaskCheckboxes() {
    var items = document.querySelectorAll('li.task-list-item');
    if (!items.length) return;
    var path = location.pathname;

    items.forEach(function (li, i) {
      var cb = li.querySelector('input[type="checkbox"]');
      if (!cb) return;
      cb.disabled = false;
      var key = 'tasklist:' + path + ':' + i;
      var saved = localStorage.getItem(key);
      if (saved === 'true') {
        cb.checked = true;
        li.classList.add('task-done');
      }
      cb.addEventListener('change', function () {
        localStorage.setItem(key, cb.checked ? 'true' : 'false');
        li.classList.toggle('task-done', cb.checked);
        updateProgress();
      });
    });
    updateProgress();
  }

  function updateProgress() {
    var lists = new Set();
    document.querySelectorAll('li.task-list-item').forEach(function (li) {
      var ul = li.parentElement;
      if (ul && ul.tagName === 'UL') lists.add(ul);
    });
    lists.forEach(function (list) {
      var taskItems = list.querySelectorAll(':scope > li.task-list-item');
      if (!taskItems.length) return;
      var checked = 0;
      taskItems.forEach(function (li) {
        var cb = li.querySelector('input[type="checkbox"]');
        if (cb && cb.checked) checked++;
      });
      var existing = list.previousElementSibling;
      var label;
      if (existing && existing.classList && existing.classList.contains('task-progress')) {
        label = existing;
      } else {
        label = document.createElement('div');
        label.className = 'task-progress';
        list.parentNode.insertBefore(label, list);
      }
      var pct = Math.round((checked / taskItems.length) * 100);
      label.textContent = '進捗: ' + checked + ' / ' + taskItems.length + ' (' + pct + '%)';
    });
  }

  if (typeof window.document$ !== 'undefined' && typeof window.document$.subscribe === 'function') {
    window.document$.subscribe(setupTaskCheckboxes);
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupTaskCheckboxes);
  } else {
    setupTaskCheckboxes();
  }
})();
