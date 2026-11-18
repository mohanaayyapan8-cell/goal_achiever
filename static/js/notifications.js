// Runs on every logged-in page: asks the server for news once a minute (this also creates due
// reminders while the tab is open), updates the bell, and shows a browser pop-up for new
// notifications IF the user enabled it and allowed it. It only works while the site is open in a tab.
(function () {
  var body = document.body, url = body.dataset.pollUrl;
  if (!url) return;
  var canPopup = body.dataset.browserNotify === "1" && ("Notification" in window) && Notification.permission === "granted";
  var KEY = "ga-shown-notifications", shown = [];
  try { shown = JSON.parse(localStorage.getItem(KEY) || "[]"); } catch (e) { shown = []; }

  function remember() { try { localStorage.setItem(KEY, JSON.stringify(shown.slice(-200))); } catch (e) { /* storage unavailable */ } }

  function updateBell(count) {
    var bell = document.getElementById("bell-count");
    if (!bell) return;
    bell.textContent = count; bell.hidden = count === 0;
  }

  function popup(item) {
    try {
      var n = new Notification(item.title, { body: item.message, tag: "ga-" + item.id });
      n.onclick = function () { window.focus(); if (item.link) window.location.href = item.link; };
    } catch (e) { /* some browsers block constructing notifications */ }
  }

  function poll() {
    fetch(url, { credentials: "same-origin", headers: { "Accept": "application/json" } })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data) return;
        updateBell(data.unread);
        if (!canPopup) return;
        data.items.forEach(function (item) {
          if (shown.indexOf(item.id) !== -1) return;
          shown.push(item.id); popup(item);
        });
        remember();
      })
      .catch(function () { /* offline: try again next minute */ });
  }
  poll();
  setInterval(poll, 60000);
})();
