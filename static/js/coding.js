// DSA practice page: editor helpers and "Run tests in browser" (sandboxed in a Web Worker).
(function () {
  var dataEl = document.getElementById("problem-data");
  if (!dataEl) return;
  var cfg = JSON.parse(dataEl.textContent);
  var $ = function (id) { return document.getElementById(id); };
  var form = $("code-form"), editor = $("editor"), runBtn = $("btn-run"), resetBtn = $("btn-reset"),
      statusEl = $("run-status"), resultsEl = $("results");
  var token = form.querySelector("input[name=csrfmiddlewaretoken]").value;
  var worker = null, ready = false, running = false, runTimer = null, loadTimer = null;

  // Tab key inserts spaces in the editor
  editor.addEventListener("keydown", function (e) {
    if (e.key !== "Tab" || e.shiftKey) return;
    e.preventDefault();
    var s = editor.selectionStart;
    editor.value = editor.value.slice(0, s) + "    " + editor.value.slice(editor.selectionEnd);
    editor.selectionStart = editor.selectionEnd = s + 4;
  });
  resetBtn.addEventListener("click", function () {
    if (window.confirm("Replace your code with the starter code?")) editor.value = cfg.starter;
  });

  function setStatus(t) { statusEl.textContent = t; }
  function el(tag, cls, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text !== undefined) n.textContent = text; return n; }

  function stopWorker() {
    if (worker) { worker.terminate(); worker = null; }
    ready = false; clearTimeout(runTimer); clearTimeout(loadTimer);
  }
  function done() { running = false; runBtn.disabled = false; clearTimeout(runTimer); clearTimeout(loadTimer); }

  function fail(message, reportAsFailed) {
    done(); stopWorker();
    setStatus(message);
    if (reportAsFailed) report({ passed: 0, total: cfg.tests.length, details: [], error: message, stdout: "" });
  }

  function render(res) {
    resultsEl.textContent = "";
    if (res.error) resultsEl.appendChild(el("p", "error-text", res.error));
    var passed = 0;
    res.results.forEach(function (r) {
      if (r.passed) passed++;
      var row = el("div", "test-row " + (r.passed ? "ok" : "no"));
      row.appendChild(el("strong", "", "Test " + (r.index + 1) + ": " + (r.passed ? "PASS" : "FAIL")));
      var visible = r.index < 2;
      if (!r.passed) {
        var detail = r.error ? r.error : (visible ? "got " + r.got + ", expected " + JSON.stringify(cfg.tests[r.index].expected)
                                                   : "hidden test: your output was different");
        row.appendChild(el("div", "muted", detail));
      }
      resultsEl.appendChild(row);
    });
    if (res.stdout) { resultsEl.appendChild(el("h4", "", "Your print output")); resultsEl.appendChild(el("pre", "answer-text", res.stdout)); }
    return passed;
  }

  function report(payload) {
    var body = new FormData();
    body.append("action", "browser_result"); body.append("code", editor.value); body.append("result", JSON.stringify(payload));
    fetch(cfg.submitUrl, { method: "POST", body: body, headers: { "X-CSRFToken": token }, credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (j) { resultsEl.appendChild(el("p", j.solved ? "score-good" : "muted", j.message || "")); })
      .catch(function () { resultsEl.appendChild(el("p", "muted", "Could not save the result to your history (offline?).")); });
  }

  function finish(res) {
    done();
    var passed = render(res);
    var total = cfg.tests.length;
    setStatus(res.error ? "Your code has a problem." : passed + " of " + total + " tests passed.");
    report({ passed: passed, total: total, error: res.error || "", stdout: res.stdout || "",
             details: res.results.map(function (r) { return { i: r.index, p: r.passed, e: r.error || "" }; }) });
  }

  function sendRun() {
    setStatus("Running tests…");
    worker.postMessage({ type: "run", code: editor.value, fn: cfg.fn, tests: cfg.tests });
    runTimer = setTimeout(function () {
      fail("Time limit exceeded (" + (cfg.timeoutMs / 1000) + " s). Your code may contain an infinite loop.", true);
    }, cfg.timeoutMs);
  }

  function startWorker() {
    setStatus("Starting the Python sandbox (the first run takes a few seconds)…");
    try { worker = new Worker(cfg.workerUrl); } catch (err) { fail("Your browser could not start the sandbox. Use manual mode below.", false); return; }
    worker.onmessage = function (e) {
      var m = e.data;
      if (m.type === "ready") { clearTimeout(loadTimer); ready = true; sendRun(); }
      else if (m.type === "result") { clearTimeout(runTimer); finish(m.result); }
      else if (m.type === "error") { fail("Sandbox error: " + m.message, false); }
    };
    worker.onerror = function () { fail("The Python sandbox could not start (offline or blocked). Use manual mode below.", false); };
    loadTimer = setTimeout(function () { fail("The sandbox took too long to start. Use manual mode below.", false); }, 60000);
    worker.postMessage({ type: "init", base: new URL(cfg.pyodideBase, window.location.href).href, harnessUrl: cfg.harnessUrl });
  }

  runBtn.addEventListener("click", function () {
    if (running) return;
    if (!editor.value.trim()) { setStatus("Write some code first."); return; }
    running = true; runBtn.disabled = true; resultsEl.textContent = "";
    if (!worker) startWorker(); else if (ready) sendRun();
  });
})();
