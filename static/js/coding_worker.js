// Web Worker: loads Pyodide (Python in WebAssembly) and runs the test harness on the student's code.
// It runs in the student's own browser. The Django server never sees or runs this code.
var pyodide = null;

self.onmessage = async function (e) {
  var m = e.data;
  try {
    if (m.type === "init") {
      importScripts(m.base + "pyodide.js");
      pyodide = await loadPyodide({ indexURL: m.base });
      var src = await (await fetch(m.harnessUrl, { credentials: "same-origin" })).text();
      pyodide.runPython(src);                       // defines run_tests()
      self.postMessage({ type: "ready" });
    } else if (m.type === "run") {
      pyodide.globals.set("_code", m.code);
      pyodide.globals.set("_fn", m.fn);
      pyodide.globals.set("_tests", JSON.stringify(m.tests));
      var out = pyodide.runPython("import json\njson.dumps(run_tests(_code, _fn, json.loads(_tests)))");
      self.postMessage({ type: "result", result: JSON.parse(out) });
    }
  } catch (err) {
    self.postMessage({ type: "error", message: String((err && err.message) || err) });
  }
};
