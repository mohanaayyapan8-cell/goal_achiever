// End-to-end test of the browser sandbox flow with the REAL worker script and REAL Pyodide:
// coding.js (stubbed page) -> worker -> Pyodide -> harness -> results -> report to server (stubbed fetch).
// Usage: PYODIDE_PKG=/path/to/node_modules/pyodide node tests_js/test_coding_flow.js problems.json
const fs = require("fs"), path = require("path"), assert = require("assert");
const root = path.resolve(__dirname, "..");
const vendor = path.join(root, "static/js/vendor/pyodide") + "/";
const { loadPyodide: realLoad } = require(process.env.PYODIDE_PKG || "pyodide");
const problems = JSON.parse(fs.readFileSync(process.argv[2] || "/tmp/problems.json", "utf8"));
const problem = problems.find(p => p.slug === "two-sum");

// ---- load the real worker script once, with a fake worker global
const workerSelf = { postMessage: null, onmessage: null };
global.loadPyodide = (opts) => realLoad({ ...opts, indexURL: vendor });
global.fetch = async () => ({ text: async () => fs.readFileSync(path.join(root, "coding/harness.py"), "utf8") });
new Function("self", "importScripts", fs.readFileSync(path.join(root, "static/js/coding_worker.js"), "utf8"))(workerSelf, () => {});

class FakeWorker {
  static mode = "real";
  constructor() { this.terminated = false; FakeWorker.last = this; workerSelf.postMessage = (m) => { if (!this.terminated) setImmediate(() => this.onmessage && this.onmessage({ data: m })); }; }
  postMessage(m) { if (FakeWorker.mode === "hang" && m.type === "run") return; setImmediate(() => workerSelf.onmessage({ data: m })); }
  terminate() { this.terminated = true; }
}

// ---- tiny fake DOM
class El {
  constructor(tag) { this.tag = tag; this.children = []; this.className = ""; this._text = ""; this.value = ""; this.disabled = false; this.listeners = {}; }
  set textContent(v) { this._text = v; if (v === "") this.children = []; }
  get textContent() { return this._text + this.children.map(c => c.textContent).join(" "); }
  appendChild(c) { this.children.push(c); return c; }
  addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); }
  fire(t, e) { (this.listeners[t] || []).forEach(f => f(e || {})); }
  querySelector() { return { value: "csrf-token" }; }
}

async function scenario(name, code, opts = {}) {
  FakeWorker.mode = opts.mode || "real";
  const ids = {};
  ["problem-data", "code-form", "editor", "btn-run", "btn-reset", "run-status", "results"].forEach(i => ids[i] = new El("x"));
  const cfg = { fn: problem.function_name, timeoutMs: opts.timeoutMs || 20000, tests: problem.tests, examples: [], starter: problem.starter_code,
                workerUrl: "w.js", pyodideBase: "/static/js/vendor/pyodide/", harnessUrl: "/h.py", submitUrl: "/submit/" };
  ids["problem-data"].textContent = JSON.stringify(cfg);
  ids["editor"].value = code;
  const posted = [];
  global.document = { getElementById: id => ids[id], createElement: t => new El(t) };
  global.window = { confirm: () => true, location: { href: "http://localhost/" } };
  global.URL = URL; global.Worker = FakeWorker;
  global.FormData = class { constructor() { this.m = {}; } append(k, v) { this.m[k] = v; } };
  global.fetch = async (url, init) => {
    if (String(url).endsWith(".py")) return { text: async () => fs.readFileSync(path.join(root, "coding/harness.py"), "utf8") };   // the worker asks for the harness
    posted.push(init.body.m);                                                                                                  // coding.js reports a result
    return { json: async () => ({ ok: true, solved: JSON.parse(init.body.m.result).passed === cfg.tests.length, message: "saved" }) };
  };
  delete require.cache[path.join(root, "static/js/coding.js")];
  eval(fs.readFileSync(path.join(root, "static/js/coding.js"), "utf8"));
  ids["btn-run"].fire("click");
  for (let i = 0; i < 600 && posted.length === 0; i++) await new Promise(r => setTimeout(r, 50));
  assert(posted.length === 1, name + ": no result was reported");
  const payload = JSON.parse(posted[0].result);
  assert.strictEqual(posted[0].action, "browser_result"); assert.strictEqual(posted[0].code, code);
  return { payload, status: ids["run-status"].textContent, results: ids["results"].textContent, ids };
}

(async () => {
  const pass = await scenario("pass", problem.solution);
  assert.strictEqual(pass.payload.passed, problem.tests.length); assert.strictEqual(pass.payload.error, "");
  assert(/tests passed/.test(pass.status), pass.status);

  const fail = await scenario("fail", problem.starter_code);
  assert(fail.payload.passed < problem.tests.length); assert(/FAIL/.test(fail.results));
  assert(fail.payload.details.length === problem.tests.length);

  const syn = await scenario("syntax", "def two_sum(nums, target)\n    return []");
  assert(/SyntaxError/.test(syn.payload.error), syn.payload.error); assert.strictEqual(syn.payload.passed, 0);

  const exc = await scenario("exception", "def two_sum(nums, target):\n    return nums[99]\n");
  assert(exc.payload.passed === 0 && /IndexError/.test(exc.results), exc.results);

  const prints = await scenario("prints", "def two_sum(nums, target):\n    print('hello from my code')\n    return []\n");
  assert(/hello from my code/.test(prints.results));

  const hang = await scenario("timeout", "while True:\n    pass\n", { mode: "hang", timeoutMs: 200 });
  assert(/Time limit exceeded/.test(hang.payload.error), hang.payload.error);
  assert(FakeWorker.last.terminated, "worker should be terminated after a timeout");
  console.log("coding flow test: pass, fail, syntax error, exception, print capture, timeout all OK");
  process.exit(0);
})().catch(e => { console.error("FAILED:", e.message); process.exit(1); });
