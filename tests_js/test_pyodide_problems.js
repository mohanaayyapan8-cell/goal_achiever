// Runs every practice problem's reference solution (and starter code) inside Pyodide,
// the same engine the browser uses, with the same harness.py. Usage:
//   npm install pyodide@0.26.4   (once, anywhere)  then:  node tests_js/test_pyodide_problems.js problems.json
const fs = require("fs"), path = require("path");
const root = path.resolve(__dirname, "..");
(async () => {
  const { loadPyodide } = require(process.env.PYODIDE_PKG || "pyodide");
  const py = await loadPyodide({ indexURL: path.join(root, "static/js/vendor/pyodide") + "/" });
  py.runPython(fs.readFileSync(path.join(root, "coding/harness.py"), "utf8"));
  const problems = JSON.parse(fs.readFileSync(process.argv[2] || "/tmp/problems.json", "utf8"));
  let bad = 0;
  for (const p of problems) {
    for (const [label, code] of [["solution", p.solution], ["starter", p.starter_code]]) {
      py.globals.set("_code", code); py.globals.set("_fn", p.function_name); py.globals.set("_tests", JSON.stringify(p.tests));
      const res = JSON.parse(py.runPython("import json\njson.dumps(run_tests(_code, _fn, json.loads(_tests)))"));
      const passed = res.results.filter(r => r.passed).length;
      const expectAll = label === "solution";
      const ok = res.error === null && (expectAll ? passed === p.tests.length : passed < p.tests.length);
      if (!ok) { bad++; console.log("PROBLEM", p.slug, label, res.error, passed + "/" + p.tests.length); }
    }
  }
  // infinite recursion and exceptions are reported, not fatal
  py.globals.set("_code", "def f(n):\n    return f(n)\n"); py.globals.set("_fn", "f"); py.globals.set("_tests", JSON.stringify([{args:[1],expected:1}]));
  const rec = JSON.parse(py.runPython("import json\njson.dumps(run_tests(_code,_fn,json.loads(_tests)))"));
  if (rec.results[0].passed || !/RecursionError/.test(rec.results[0].error)) { bad++; console.log("recursion not reported", rec); }
  console.log(`Pyodide check: ${problems.length} problems, ${bad} issues`);
  process.exit(bad ? 1 : 0);
})();
