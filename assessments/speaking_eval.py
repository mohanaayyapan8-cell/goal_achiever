"""Transparent scoring of a SPOKEN answer from its TRANSCRIPT TEXT only.

Honest limits: pronunciation, accent, tone, volume and confidence are NOT
measured. Speech recognition usually gives text without punctuation, so
punctuation and capital letters are not judged for speech transcripts."""
import re

CRITERIA = ("concept_clarity", "relevance", "grammar", "sentence_formation", "vocabulary", "fluency", "completeness")
LABELS = {"concept_clarity": "Concept clarity", "relevance": "Answer relevance", "grammar": "Grammar",
          "sentence_formation": "Sentence formation", "vocabulary": "Vocabulary", "fluency": "Fluency (transcript smoothness)",
          "completeness": "Answer completeness"}
WEIGHTS = {"concept_clarity": 20, "relevance": 15, "grammar": 15, "sentence_formation": 10,
           "vocabulary": 10, "fluency": 15, "completeness": 15}
LIMITATIONS = ("Scores are estimated from the text of your answer only. Pronunciation, accent, tone and "
               "confidence are not measured, and the grammar check is a small set of common-mistake rules, "
               "not a full grammar checker.")

FILLERS = [r"\bum+\b", r"\buh+\b", r"\berm?\b", r"\bah+\b", r"\byou know\b", r"\bi mean\b", r"\bkind of\b",
           r"\bsort of\b", r"\bbasically\b", r"\bactually\b"]
CONNECTORS = ["because", "so that", "so", "if", "when", "for example", "for instance", "first", "then", "finally",
              "which", "that", "therefore", "while", "but", "also", "after", "such as", "next"]
EXAMPLE_RE = re.compile(r"\b(example|for instance|such as|suppose|imagine|let'?s say|real[- ]time|real[- ]life)\b", re.I)
# (pattern, message, case_sensitive)
GRAMMAR_RULES = [
    # lowercase "i" counts as the pronoun only before a typical verb (so the loop variable i is not flagged)
    (r"\bi\b(?=\s+(?:am|was|have|had|will|would|think|know|want|can|could|do|did|don't|didn't|like|need|use|see|say|should|believe|learn|make|feel|mean|prefer|wrote|write|used)\b|['’](?:m|ll|ve|d)\b)",
     "Write the pronoun “I” with a capital letter.", True),
    (r"\b(he|she|it)\s+(don't|do not|are|were|have)\b", "With he/she/it use “doesn't”, “is”, “was” or “has”.", False),
    (r"\b(they|we|you|people|students)\s+(is|was|has|doesn't|does not)\b", "With they/we/you or a plural noun use “are”, “were”, “have” or “don't”.", False),
    (r"\bI\s+(is|are|has|does)\b", "With “I” use “am”, “have” or “do”.", True),
    (r"\b(informations|equipments|advices|furnitures|knowledges)\b", "This noun is uncountable and has no plural form.", False),
    (r"\bmore\s+(better|easier|faster|simpler|bigger)\b", "Do not use “more” with a comparative word.", False),
    (r"\bcan\s+able\s+to\b", "Say “can” or “is able to”, not “can able to”.", False),
]
A_BEFORE_VOWEL = re.compile(r"\ba\s+(?!(?:us|uni|use|eu|one|once|ubiq|uk\b)\w*)([aeiou]\w*)", re.I)
AN_BEFORE_CONS = re.compile(r"\ban\s+([bcdgjkpqtvwyz]\w*)", re.I)


def tokens(text):
    return re.findall(r"[A-Za-z']+", text.lower())


def _clamp(v):
    return int(round(max(0, min(100, v))))


def _has_punctuation(text):
    return bool(re.search(r"[.!?]", text))


def _sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text.strip()) if s.strip()]


def _coverage(points, text):
    hits = [any(re.search(p, text, re.I | re.S) for p in pt["any"]) for pt in points]
    return hits


def evaluate_speaking(q, text, input_method="typed", seconds=0):
    text = (text or "").strip()
    words = tokens(text)
    n = len(words)
    low = text.lower()
    punct = _has_punctuation(text)
    judge_punct = punct or input_method != "speech"
    notes = {k: [] for k in CRITERIA}
    issues = []

    # ---- concept clarity & relevance
    points = q.get("points") or []
    hits = _coverage(points, text) if points else []
    term_hits = sum(1 for t in q.get("terms", []) if re.search(t, low))
    need = min(2, len(q.get("terms", []))) or 1
    if points:
        concept = 100 * sum(hits) / len(points)
        missed = [pt["label"] for pt, ok in zip(points, hits) if not ok]
        notes["concept_clarity"].append(f"Key points covered: {sum(hits)} of {len(points)}." + (f" Missing: {'; '.join(missed)}." if missed else ""))
    else:
        concept = min(100, 40 + 20 * term_hits) if n else 0
        notes["concept_clarity"].append("No fixed key points for this topic, so this is based on topic words only. Compare with your lesson.")
    relevance = min(100, 100 * term_hits / need) if n else 0
    notes["relevance"].append(f"Topic words used: {term_hits} (aim for at least {need}).")

    # ---- grammar
    for pattern, message, cs in GRAMMAR_RULES:
        for m in re.finditer(pattern, text, 0 if cs else re.I):
            issues.append({"text": m.group(0), "message": message})
    for m in A_BEFORE_VOWEL.finditer(text):
        issues.append({"text": m.group(0), "message": "Use “an” before a vowel sound."})
    for m in AN_BEFORE_CONS.finditer(text):
        issues.append({"text": m.group(0), "message": "Use “a” before a consonant sound."})
    sentences = _sentences(text) if punct else []
    if judge_punct and n >= 5:
        if not punct:
            issues.append({"text": "(whole answer)", "message": "Add full stops so the sentences can be checked."})
        for s in sentences[:12]:
            if s[0].isalpha() and s[0].islower():
                issues.append({"text": s[:30], "message": "Start the sentence with a capital letter."})
    issues = issues[:10]
    grammar = 100 - 12 * len(issues) if n else 0
    if input_method == "speech" and not punct:
        notes["grammar"].append("Speech recognition adds no punctuation, so capital letters and full stops were not judged.")
    notes["grammar"].append(f"Common-mistake rules triggered: {len(issues)}.")

    # ---- sentence formation
    connectors = {c for c in CONNECTORS if re.search(rf"\b{re.escape(c)}\b", low)}
    if punct and sentences:
        lens = [len(tokens(s)) for s in sentences]
        fragments = sum(1 for L in lens if L < 4) / len(lens)
        runons = sum(1 for L in lens if L > 40) / len(lens)
        sentence = 100 - 40 * fragments - 30 * runons - (15 if not connectors else 0) - (15 if sum(lens) / len(lens) < 6 else 0)
        notes["sentence_formation"].append(f"{len(sentences)} sentences, average {sum(lens) / len(lens):.0f} words; linking words used: {len(connectors)}.")
    else:
        sentence = 50 + 15 * min(len(connectors), 3) + (5 if n >= 30 else 0) if n else 0
        notes["sentence_formation"].append("Sentence boundaries could not be seen (no punctuation), so this is estimated from linking words and length. Add full stops when you edit to get a fuller check.")

    # ---- vocabulary
    if n:
        ttr = len(set(words)) / n
        variety = max(0, min(1, (ttr - 0.4) / 0.3)) * 60
        terms = min(1, term_hits / need) * 40 if q.get("terms") else 40
        vocabulary = variety + terms
        notes["vocabulary"].append(f"{len(set(words))} different words in {n} (variety {ttr:.0%}); topic terms used: {term_hits}.")
    else:
        vocabulary = 0

    # ---- fluency (smoothness of the transcript only)
    fillers = sum(len(re.findall(p, low)) for p in FILLERS)
    repeats = len([m for m in re.findall(r"\b(\w+)\s+\1\b", low) if m not in ("that", "had")])
    fluency = 100 - min(40, 400 * fillers / max(n, 1)) - min(30, 8 * repeats) if n else 0
    notes["fluency"].append(f"Filler words: {fillers}; repeated words: {repeats}.")
    wpm = None
    if input_method == "speech" and seconds >= 10 and n:
        wpm = round(n * 60 / seconds)
        ideal = 1.0 if 90 <= wpm <= 170 else (wpm / 90 if wpm < 90 else 170 / wpm)
        fluency -= 30 * (1 - ideal)
        notes["fluency"].append(f"Speaking pace about {wpm} words per minute (comfortable range 90 to 170).")
    else:
        notes["fluency"].append("Pace was not measured (typed answer or too short a recording).")

    # ---- completeness
    target = q.get("target_words", 50)
    example_ok = (not q.get("needs_example")) or bool(EXAMPLE_RE.search(text))
    cover = (sum(hits) / len(hits)) if points else min(1, term_hits / need)
    completeness = 100 * (.5 * min(1, n / target) + .3 * cover + .2 * (1 if example_ok else 0)) if n else 0
    notes["completeness"].append(f"{n} words (aim for about {target}).")
    if q.get("needs_example"):
        notes["completeness"].append("Example included." if example_ok else "The question asks for an example: add one.")

    criteria = {"concept_clarity": _clamp(concept), "relevance": _clamp(relevance), "grammar": _clamp(grammar),
                "sentence_formation": _clamp(sentence), "vocabulary": _clamp(vocabulary),
                "fluency": _clamp(fluency), "completeness": _clamp(completeness)}
    overall = round(sum(criteria[k] * WEIGHTS[k] for k in CRITERIA) / sum(WEIGHTS.values()), 1)
    tips = []
    if n < target:
        tips.append(f"Say a little more: your answer has {n} words and the target is about {target}.")
    if q.get("needs_example") and not example_ok:
        tips.append("Finish with a short real-time example.")
    if fillers:
        tips.append("Pause silently instead of using filler words such as “um” or “basically”.")
    if issues:
        tips.append("Review the grammar notes below and say the sentence again correctly.")
    if points and sum(hits) < len(points):
        tips.append("Cover every key point listed under concept clarity.")
    return {"overall": overall, "criteria": criteria,
            "details": {"notes": notes, "issues": issues, "tips": tips, "limitations": LIMITATIONS,
                        "stats": {"words": n, "fillers": fillers, "repeats": repeats, "wpm": wpm,
                                  "input_method": input_method}}}
