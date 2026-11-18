// Timed aptitude test: countdown, autosave of each answer, auto-submit at 0:00.
(function () {
  var root = document.getElementById("test-root");
  if (!root) return;
  var form = document.getElementById("test-form"), timerEl = document.getElementById("timer"),
      answeredEl = document.getElementById("answered"), msg = document.getElementById("time-msg"),
      token = form.querySelector("input[name=csrfmiddlewaretoken]").value,
      deadline = Date.now() + parseInt(root.dataset.remaining, 10) * 1000,
      total = parseInt(root.dataset.total, 10), submitted = false;

  function pad(n) { return (n < 10 ? "0" : "") + n; }
  function countAnswered() {
    var names = {};
    form.querySelectorAll("input[type=radio]:checked").forEach(function (r) { names[r.name] = 1; });
    answeredEl.textContent = Object.keys(names).length;
    return Object.keys(names).length;
  }
  function submitNow() {
    if (submitted) return;
    submitted = true;
    form.submit();
  }
  function tick() {
    var left = Math.max(0, Math.round((deadline - Date.now()) / 1000));
    timerEl.textContent = pad(Math.floor(left / 60)) + ":" + pad(left % 60);
    timerEl.classList.toggle("timer-low", left <= 60);
    if (left <= 0) {
      msg.hidden = false; msg.textContent = "Time is up. Submitting your answers…";
      submitNow();
    }
  }
  setInterval(tick, 500); tick();

  function save(index, option) {
    var body = new FormData();
    body.append("index", index); body.append("option", option === null ? "" : option);
    fetch(root.dataset.autosaveUrl, { method: "POST", body: body, headers: { "X-CSRFToken": token }, credentials: "same-origin" })
      .then(function (r) {
        if (r.status === 409) { msg.hidden = false; msg.textContent = "Time is up. Submitting your answers…"; submitNow(); }
      })
      .catch(function () { /* offline: answers are still sent when you submit */ });
  }

  form.addEventListener("change", function (e) {
    if (e.target.type !== "radio") return;
    countAnswered();
    save(e.target.dataset.index, e.target.value);
  });
  form.querySelectorAll(".clear-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      form.querySelectorAll("input[name=q" + btn.dataset.index + "]").forEach(function (r) { r.checked = false; });
      countAnswered(); save(btn.dataset.index, null);
    });
  });
  form.addEventListener("submit", function (e) {
    if (submitted) return;
    var n = countAnswered();
    if (n < total && !window.confirm("You answered " + n + " of " + total + " questions. Submit the test now?")) { e.preventDefault(); return; }
    submitted = true;
  });
  countAnswered();
})();
