// Dark/light theme toggle. The choice is remembered in this browser only.
(function () {
  var root = document.documentElement;
  var button = document.getElementById("theme-toggle");
  var label = document.getElementById("theme-toggle-label");
  if (!button) return;

  function refreshLabel() {
    label.textContent = root.getAttribute("data-theme") === "dark" ? "Light mode" : "Dark mode";
  }

  button.addEventListener("click", function () {
    var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try { localStorage.setItem("ga-theme", next); } catch (e) {}
    refreshLabel();
    document.dispatchEvent(new Event("ga:themechange")); // charts re-colour themselves
  });

  refreshLabel();
})();
