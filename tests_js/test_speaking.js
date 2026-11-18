// Stubbed-browser test of speaking.js
const fs = require("fs");
function el(extra) { const l = {}; return Object.assign({ value: "", textContent: "", hidden: false, disabled: false, title: "",
  addEventListener(t, f) { (l[t] = l[t] || []).push(f); }, fire(t, e) { (l[t] || []).forEach(f => f(e || {})); },
  getAttribute() { return "confirm?"; }, querySelector() { return ids["submit"]; } }, extra); }
const ids = {};
["speaking-form","question-text","btn-read","btn-start","btn-stop","final_text","raw_transcript","input_method",
 "speaking_seconds","rec-status","lang","support-note","submit"].forEach(i => ids[i] = el());
ids["question-text"].textContent = "  Explain loops.  "; ids["lang"].value = "en-IN"; ids["input_method"].value = "typed";
ids["final_text"].value = "typed first.";
global.document = { getElementById: id => ids[id] };
let spoken = [];
global.SpeechSynthesisUtterance = function (t) { this.text = t; };
global.window = { confirm: () => true, speechSynthesis: { cancel() {}, speak(u) { spoken.push(u.text + "|" + u.lang); } } };
let rec;
window.webkitSpeechRecognition = function () { rec = this; this.start = () => { this.started = true; }; this.stop = () => { this.onend && this.onend(); }; };
eval(fs.readFileSync(__dirname + "/../static/js/speaking.js", "utf8").replace(/^/, ""));
const assert = require("assert");
// read aloud
ids["btn-read"].fire("click"); assert.deepStrictEqual(spoken, ["Explain loops.|en-IN"]);
// start
ids["btn-start"].fire("click"); assert(rec.started); assert(ids["btn-stop"].disabled === false); assert(ids["btn-start"].disabled === true);
// interim then final results
rec.onresult({ resultIndex: 0, results: [Object.assign([{ transcript: "a for loop" }], { isFinal: false })] });
assert.strictEqual(ids["final_text"].value, "typed first. a for loop");
rec.onresult({ resultIndex: 0, results: [Object.assign([{ transcript: "a for loop repeats code" }], { isFinal: true })] });
assert.strictEqual(ids["final_text"].value, "typed first. a for loop repeats code");
assert.strictEqual(ids["input_method"].value, "speech");
assert.strictEqual(ids["raw_transcript"].value, "a for loop repeats code");
// stop + submit
ids["btn-stop"].fire("click"); assert(ids["btn-start"].disabled === false);
ids["speaking-form"].fire("submit"); assert(Number(ids["speaking_seconds"].value) >= 0);
// error path keeps its message
ids["btn-start"].fire("click"); rec.onerror({ error: "not-allowed" }); rec.onend();
assert(/permission was denied/.test(ids["rec-status"].textContent), ids["rec-status"].textContent);
console.log("speaking.js stub test: all assertions passed");
