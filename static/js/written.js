// Written assessment helpers: Tab key in code boxes, and a confirm before submitting.
(function () {
  document.querySelectorAll("textarea[data-code]").forEach(function (box) {
    box.addEventListener("keydown", function (e) {
      if (e.key !== "Tab" || e.shiftKey) return;
      e.preventDefault();                       // keep focus in the editor
      var s = box.selectionStart, end = box.selectionEnd;
      box.value = box.value.slice(0, s) + "    " + box.value.slice(end);
      box.selectionStart = box.selectionEnd = s + 4;
    });
  });
  document.querySelectorAll("[data-confirm]").forEach(function (btn) {
    btn.addEventListener("click", function (e) {
      if (!window.confirm(btn.getAttribute("data-confirm"))) e.preventDefault();
    });
  });
})();
