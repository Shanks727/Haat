// Small progressive enhancements – the site works without JavaScript too.
(function () {
  // Dismiss flash messages
  document.addEventListener('click', function (e) {
    if (e.target.classList.contains('flash-x')) e.target.parentElement.remove();
  });

  // Ask before destructive actions: <form data-confirm="...">
  document.querySelectorAll('form[data-confirm]').forEach(function (f) {
    f.addEventListener('submit', function (e) {
      if (!window.confirm(f.dataset.confirm)) e.preventDefault();
    });
  });

  // Auto-submit selects marked data-autosubmit
  document.querySelectorAll('select[data-autosubmit]').forEach(function (s) {
    s.addEventListener('change', function () { s.form.submit(); });
  });

  // Quantity steppers
  document.querySelectorAll('[data-qty]').forEach(function (box) {
    var input = box.querySelector('input');
    var autosubmit = box.hasAttribute('data-autosubmit-qty');
    var timer;
    function commit() {
      if (!autosubmit) return;
      clearTimeout(timer);
      timer = setTimeout(function () { input.form.submit(); }, 450);
    }
    box.querySelectorAll('[data-step]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var min = parseInt(input.min || '0', 10), max = parseInt(input.max || '9999', 10);
        var v = (parseInt(input.value, 10) || 0) + parseInt(btn.dataset.step, 10);
        input.value = Math.max(min, Math.min(max, v));
        commit();
      });
    });
    input.addEventListener('change', commit);
  });
})();
