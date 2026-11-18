// Reminder settings page: shows the browser's notification permission and lets the user request it.
(function () {
  var status = document.getElementById("perm-status"), btn = document.getElementById("perm-btn");
  if (!status) return;
  var texts = { granted: "allowed", denied: "blocked (change this in your browser's site settings)", "default": "not asked yet" };
  function show() {
    if (!("Notification" in window)) { status.textContent = "not supported by this browser"; btn.hidden = true; return; }
    status.textContent = texts[Notification.permission] || Notification.permission;
    btn.hidden = Notification.permission !== "default";
  }
  btn.addEventListener("click", function () {
    Notification.requestPermission().then(show);       // must come from a click, as browsers require
  });
  show();
})();
