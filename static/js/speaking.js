// Speaking assessment: read the question aloud (speechSynthesis) and dictate the answer
// (Web Speech API, where the browser supports it). Typing always works as a fallback.
(function () {
  var form = document.getElementById("speaking-form");
  if (!form) return;
  var $ = function (id) { return document.getElementById(id); };
  var textBox = $("final_text"), rawField = $("raw_transcript"), methodField = $("input_method"),
      secondsField = $("speaking_seconds"), startBtn = $("btn-start"), stopBtn = $("btn-stop"),
      readBtn = $("btn-read"), statusEl = $("rec-status"), langSel = $("lang"), note = $("support-note"),
      question = $("question-text").textContent.trim();

  // confirm before submitting
  var submitBtn = form.querySelector("[data-confirm]");
  submitBtn.addEventListener("click", function (e) {
    if (!window.confirm(submitBtn.getAttribute("data-confirm"))) e.preventDefault();
  });

  // ---- read aloud
  if (!("speechSynthesis" in window)) {
    readBtn.disabled = true;
    readBtn.title = "Your browser cannot read text aloud. Please read the question on screen.";
  } else {
    readBtn.addEventListener("click", function () {
      window.speechSynthesis.cancel();
      var u = new SpeechSynthesisUtterance(question);
      u.lang = langSel.value;
      window.speechSynthesis.speak(u);
    });
  }

  // ---- dictation
  var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    startBtn.disabled = true; stopBtn.disabled = true;
    note.hidden = false;
    note.textContent = "Speech recognition is not available in this browser (try Chrome or Edge). Please type your answer below. You can still submit it.";
    statusEl.textContent = "Typing mode";
    form.addEventListener("submit", function () { secondsField.value = 0; });
    return;
  }

  var rec = null, running = false, startedAt = 0, totalMs = 0, base = "", chunks = [], failed = false, lastError = "";

  function render(interim) {
    var parts = chunks.slice();
    if (interim && interim.trim()) parts.push(interim.trim());
    var spoken = parts.join(" ");
    textBox.value = (base + (base && spoken ? " " : "") + spoken).trim();
  }

  function addTime() {
    if (startedAt) { totalMs += Date.now() - startedAt; startedAt = 0; }
  }

  function setRunning(on) {
    running = on;
    startBtn.disabled = on; stopBtn.disabled = !on; langSel.disabled = on;
    statusEl.textContent = on ? "Listening… speak now" : "Stopped. Edit the text if needed.";
  }

  function begin() {
    rec = new SR();
    rec.lang = langSel.value; rec.continuous = true; rec.interimResults = true;
    rec.onresult = function (e) {
      var interim = "";
      for (var i = e.resultIndex; i < e.results.length; i++) {
        var r = e.results[i];
        if (r.isFinal) {
          var t = r[0].transcript.trim();
          if (t) { chunks.push(t); rawField.value = (rawField.value + " " + t).trim(); methodField.value = "speech"; }
        } else { interim += r[0].transcript; }
      }
      render(interim);
    };
    rec.onerror = function (e) {
      failed = true;
      var msg = { "not-allowed": "Microphone permission was denied. Allow the microphone, or type your answer.",
                  "service-not-allowed": "Speech service is blocked. Please type your answer.",
                  "no-speech": "No speech heard. Try again closer to the microphone.",
                  "audio-capture": "No microphone found. Please type your answer.",
                  "network": "The speech service needs an internet connection. Please type your answer." }[e.error] || ("Speech recognition error: " + e.error);
      lastError = msg;
      statusEl.textContent = msg;
    };
    rec.onend = function () {
      addTime();
      if (running && !failed) { startedAt = Date.now(); try { rec.start(); } catch (err) { setRunning(false); } }
      else { render(""); setRunning(false); if (failed && lastError) statusEl.textContent = lastError; }
    };
    startedAt = Date.now();
    rec.start();
  }

  startBtn.addEventListener("click", function () {
    failed = false; base = textBox.value.trim(); chunks = [];
    try { begin(); setRunning(true); } catch (err) { statusEl.textContent = "Could not start the microphone. Please type your answer."; }
  });

  function stop() {
    if (!running) return;
    running = false;
    try { rec.stop(); } catch (err) { /* already stopped */ }
    addTime();
    render("");
    setRunning(false);
  }
  stopBtn.addEventListener("click", stop);

  form.addEventListener("submit", function () {
    if (running) stop();
    secondsField.value = Math.round(totalMs / 1000);
  });
})();
