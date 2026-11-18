"""Transparent resume review ("ATS checklist").

HONESTY: this is an INDICATIVE CHECKLIST SCORE built from common resume best practices. It is not an ATS
score and does not reproduce any employer's software. Every point awarded or withheld is listed with a reason.
"""
import re
from collections import Counter

DISCLAIMER = ("This is an indicative checklist score based on common resume best practices. It is NOT an ATS score: "
              "employers use different software and rules, and no tool can reproduce them. Use it as a to-do list, not a verdict.")

SECTION_SYNONYMS = {
    "summary": ["summary", "professional summary", "career summary", "objective", "career objective", "profile", "professional profile", "about me"],
    "skills": ["skills", "technical skills", "key skills", "core skills", "core competencies", "skills and tools", "technologies"],
    "experience": ["experience", "work experience", "professional experience", "internships", "internship", "internship experience", "employment", "employment history", "work history"],
    "education": ["education", "academic background", "academic qualifications", "qualifications", "education and training"],
    "projects": ["projects", "academic projects", "personal projects", "key projects", "project work", "projects and research"],
    "certifications": ["certifications", "certificates", "licenses and certifications", "courses and certifications", "courses"],
    "achievements": ["achievements", "accomplishments", "awards", "awards and honors", "honors and awards", "achievements and awards"],
}
HEADING_LOOKUP = {p: k for k, ps in SECTION_SYNONYMS.items() for p in ps}
SECTION_LABELS = {"summary": "Summary or objective", "skills": "Skills", "experience": "Experience / internships", "education": "Education",
                  "projects": "Projects", "certifications": "Certifications", "achievements": "Achievements"}

# (canonical skill, aliases). Aliases are matched as whole words (c++, c#, node.js handled).
VOCAB = [
    ("python", ["python"]), ("java", ["java"]), ("javascript", ["javascript", "js"]), ("typescript", ["typescript"]), ("c++", ["c++"]),
    ("c#", ["c#"]), ("sql", ["sql"]), ("html", ["html", "html5"]), ("css", ["css", "css3"]), ("django", ["django"]), ("flask", ["flask"]),
    ("fastapi", ["fastapi"]), ("react", ["react", "reactjs", "react.js"]), ("angular", ["angular"]), ("node.js", ["node.js", "nodejs", "node js"]),
    ("spring boot", ["spring boot", "springboot"]), ("bootstrap", ["bootstrap"]), ("pandas", ["pandas"]), ("numpy", ["numpy"]),
    ("matplotlib", ["matplotlib"]), ("scikit-learn", ["scikit-learn", "sklearn"]), ("tensorflow", ["tensorflow"]), ("pytorch", ["pytorch"]),
    ("excel", ["excel", "ms excel", "microsoft excel"]), ("power bi", ["power bi", "powerbi"]), ("tableau", ["tableau"]),
    ("statistics", ["statistics", "statistical"]), ("etl", ["etl"]), ("data cleaning", ["data cleaning", "data cleansing"]),
    ("data visualization", ["data visualization", "data visualisation"]), ("data analysis", ["data analysis", "data analytics"]),
    ("machine learning", ["machine learning", "ml"]), ("deep learning", ["deep learning"]), ("nlp", ["nlp", "natural language processing"]),
    ("git", ["git"]), ("github", ["github"]), ("docker", ["docker"]), ("kubernetes", ["kubernetes", "k8s"]), ("linux", ["linux"]),
    ("aws", ["aws", "amazon web services"]), ("azure", ["azure"]), ("gcp", ["gcp", "google cloud"]), ("postman", ["postman"]), ("jira", ["jira"]),
    ("rest api", ["rest api", "rest apis", "restful", "restful api", "restful apis"]), ("oop", ["oop", "oops", "object-oriented", "object oriented"]),
    ("data structures", ["data structures", "data structure", "dsa"]), ("algorithms", ["algorithms", "algorithm"]), ("agile", ["agile"]),
    ("scrum", ["scrum"]), ("unit testing", ["unit testing", "unit tests", "pytest", "unittest"]), ("ci/cd", ["ci/cd", "ci cd"]),
    ("microservices", ["microservices"]), ("system design", ["system design"]), ("debugging", ["debugging"]), ("mysql", ["mysql"]),
    ("postgresql", ["postgresql", "postgres"]), ("mongodb", ["mongodb"]), ("sqlite", ["sqlite"]), ("oracle", ["oracle"]), ("nosql", ["nosql"]),
    ("data modeling", ["data modeling", "data modelling"]), ("dax", ["dax"]), ("web development", ["web development", "web developer"]),
    ("automation", ["automation", "automated"]), ("selenium", ["selenium"]), ("prompt engineering", ["prompt engineering"]),
    ("cloud computing", ["cloud computing", "cloud"]), ("artificial intelligence", ["artificial intelligence", "ai"]),
    ("communication", ["communication", "communicate"]), ("teamwork", ["teamwork", "team player", "collaboration", "collaborate"]),
    ("problem solving", ["problem solving", "problem-solving"]), ("leadership", ["leadership"]), ("time management", ["time management"]),
    ("critical thinking", ["critical thinking"]),
]
_VOCAB_PATTERNS = {name: re.compile(r"(?<![A-Za-z0-9+#])(?:" + "|".join(re.escape(a) for a in aliases) + r")(?![A-Za-z0-9+#])", re.I)
                   for name, aliases in VOCAB}
_VOCAB_WORDS = {w for _, aliases in VOCAB for a in aliases for w in re.findall(r"[a-z]+", a)}

ROLE_SKILLS = {
    "python developer": ["python", "django", "flask", "sql", "git", "rest api", "oop", "data structures"],
    "data analyst": ["sql", "excel", "power bi", "tableau", "python", "pandas", "data visualization", "statistics"],
    "data scientist": ["python", "machine learning", "pandas", "numpy", "statistics", "sql", "scikit-learn"],
    "web developer": ["html", "css", "javascript", "react", "git", "rest api", "bootstrap"],
    "full stack": ["javascript", "react", "node.js", "sql", "rest api", "git", "docker"],
    "software engineer": ["data structures", "algorithms", "oop", "git", "sql", "system design", "unit testing"],
    "software developer": ["data structures", "algorithms", "oop", "git", "sql", "debugging", "unit testing"],
    "devops": ["docker", "kubernetes", "linux", "aws", "ci/cd", "git"],
    "business analyst": ["excel", "sql", "power bi", "communication", "agile", "data analysis"],
}
LEARNED_SKILLS = {"python": ["python"], "sql": ["sql"], "excel": ["excel"], "power bi": ["power bi"], "tableau": ["tableau"], "django": ["django"],
                  "git and github": ["git", "github"], "prompt engineering": ["prompt engineering"], "ai and ml basics": ["machine learning"],
                  "cloud computing basics": ["cloud computing"]}

ACTION_VERBS = set("""achieved administered analyzed analysed architected assembled assisted automated boosted built calculated collaborated
completed configured conducted contributed converted coordinated created debugged decreased delivered demonstrated deployed designed detected developed
directed documented drove earned enhanced engineered established evaluated executed expanded facilitated fixed founded generated guided identified
implemented improved increased initiated innovated integrated introduced investigated launched led maintained managed mentored migrated modeled
modelled monitored negotiated optimized optimised organized organised oversaw performed pioneered planned presented prioritized produced programmed
published ran reduced refactored researched resolved restructured reviewed scaled secured simplified solved spearheaded standardized streamlined
supervised supported tested trained transformed tuned upgraded validated visualized won wrote build develop design implement create lead manage
analyze automate deploy test write""".split())
WEAK_PHRASES = ["responsible for", "worked on", "helped with", "duties included", "familiar with", "assisted in", "involved in",
                "participated in", "tasked with", "was part of"]
MISSPELLINGS = {"experiance": "experience", "managment": "management", "developement": "development", "enviroment": "environment",
                "sucessful": "successful", "seperate": "separate", "recieve": "receive", "acheive": "achieve", "langauge": "language",
                "comunication": "communication", "knowlege": "knowledge", "responsibe": "responsible", "projet": "project", "algoritm": "algorithm",
                "pyhton": "python", "pyton": "python", "javascipt": "javascript", "databse": "database", "intrest": "interest", "sucess": "success",
                "colaborate": "collaborate", "implemention": "implementation", "analysys": "analysis", "analize": "analyze", "oppurtunity": "opportunity",
                "profesional": "professional", "technolgy": "technology", "certifcate": "certificate"}
STOPWORDS = set("""the and for with that this from have has had are was were will would should could can may might must you your our their they them
its into over under about across such more most other than then also been being any all each both either per via using use used etc not but
who whom whose which what when where while within without able ability strong good great excellent knowledge experience skills skill work working
team looking required preferred responsibilities requirements responsibility candidate candidates position role company years year including
include includes plus like need needs well new help make making ensure based related relevant minimum degree""".split())
ALLOWED_SYMBOLS = set("•·▪●◦–—‘’“”…▸►")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{2,5}\)?[\s.-]?){2,4}\d(?!\d)")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
BULLET_START = re.compile(r"^\s*[•·▪●◦*\-–—▸►]\s+")


# ------------------------------------------------------------------ parsing
def _norm_heading(line):
    return re.sub(r"[^a-z& ]", "", line.lower().replace("&", "and")).strip()


def scan_sections(text):
    """(sections found, non-standard headings, {section: [lines]})."""
    found, nonstd, content, current = set(), [], {}, None
    lines = [ln for ln in text.splitlines()]
    seen_content = 0
    for raw in lines:
        s = raw.strip()
        if not s:
            continue
        seen_content += 1
        key = HEADING_LOOKUP.get(_norm_heading(s)) if len(s) <= 40 else None
        if key:
            found.add(key)
            current = key
            content.setdefault(key, [])
            continue
        if (seen_content > 2 and s.isupper() and 1 <= len(s.split()) <= 4 and len(s) >= 4 and not re.search(r"[\d@|]", s)
                and s not in nonstd and not BULLET_START.match(s)):
            nonstd.append(s)
        if current:
            content[current].append(s)
    return found, nonstd[:6], content


def contact_info(text):
    emails = EMAIL_RE.findall(text)
    phone = any(10 <= len(re.sub(r"\D", "", m.group(0))) <= 13 for m in PHONE_RE.finditer(text))
    return {"email": bool(emails), "phone": phone, "linkedin": bool(re.search(r"linkedin\.com/in/", text, re.I)),
            "github": bool(re.search(r"github\.com/", text, re.I)), "portfolio": bool(re.search(r"https?://|www\.", text, re.I))}


def extract_bullets(text, content):
    explicit = [BULLET_START.sub("", ln).strip() for ln in text.splitlines() if BULLET_START.match(ln)]
    scoped = [BULLET_START.sub("", ln).strip() for sec in ("experience", "projects") for ln in content.get(sec, []) if BULLET_START.match(ln)]
    if len(scoped) >= 2:
        return scoped
    if len(explicit) >= 3:
        return explicit
    fallback = [ln for sec in ("experience", "projects") for ln in content.get(sec, []) if len(ln.split()) >= 7 and not BULLET_START.match(ln)]
    return explicit or fallback


# ------------------------------------------------------------------ keywords
def extract_keywords(job_description):
    jd = job_description or ""
    counts = Counter()
    for name, pat in _VOCAB_PATTERNS.items():
        n = len(pat.findall(jd))
        if n:
            counts[name] = n
    skills = [n for n, _ in sorted(counts.items(), key=lambda kv: (-kv[1], [v[0] for v in VOCAB].index(kv[0])))]
    words = Counter(w for w in re.findall(r"[A-Za-z][A-Za-z+#\-]{3,}", jd.lower()) if w not in STOPWORDS and w not in _VOCAB_WORDS)
    others = [w for w, n in words.most_common(30) if n >= 2][:8]
    return skills, others


def has_keyword(text, keyword):
    pat = _VOCAB_PATTERNS.get(keyword)
    if pat is None:
        pat = re.compile(r"(?<![A-Za-z0-9])" + re.escape(keyword) + r"(?![A-Za-z0-9])", re.I)
    return bool(pat.search(text))


# --------------------------------------------------------------------- writing
def writing_issues(text, bullets):
    issues = []

    def add(kind, tip, examples):
        if examples:
            issues.append({"type": kind, "tip": tip, "count": len(examples), "examples": [e[:80] for e in examples[:3]]})

    low = text.lower()
    add("Possible spelling mistake", "Check the spelling of these words.",
        [f"“{w}” (did you mean “{r}”?)" for w, r in MISSPELLINGS.items() if re.search(rf"\b{w}\b", low)])
    add("Double spaces", "Use a single space between words.", re.findall(r".{0,15}\S {2}\S.{0,15}", text))
    add("Repeated word", "A word is repeated twice in a row.",
        [m.group(0) for m in re.finditer(r"\b([A-Za-z]{2,})\s+\1\b", text, re.I) if m.group(1).lower() not in ("had", "that")])
    add("Passive voice", "Prefer active verbs, for example “Built the API” instead of “The API was built”.",
        [b for b in bullets if re.search(r"\b(was|were|been|being)\s+\w+ed\b", b, re.I)])
    if len(bullets) >= 3:
        add("Bullets not starting with a capital letter", "Start every bullet with a capital letter.", [b for b in bullets if b[:1].islower()])
        ends = sum(b.rstrip().endswith(".") for b in bullets)
        if 0.25 <= ends / len(bullets) <= 0.75:
            add("Inconsistent full stops", "Either end every bullet with a full stop or none of them.", [b for b in bullets if not b.rstrip().endswith(".")][:3])
    add("Very long bullet", "Keep bullets under about 30 words so they can be scanned quickly.", [b for b in bullets if len(b.split()) > 35])
    return issues


# ----------------------------------------------------------------- suggestions
def skill_suggestions(text, missing_keywords, target_role="", learned=()):
    """Skills worth adding, each with ALL the reasons that apply (job description, target role, what you practised)."""
    order, reasons = [], {}

    def add(skill, reason):
        if has_keyword(text, skill):
            return
        if skill not in reasons:
            order.append(skill)
            reasons[skill] = []
        if reason not in reasons[skill]:
            reasons[skill].append(reason)

    for skill in missing_keywords:
        add(skill, "Appears in the job description")
    role = (target_role or "").lower()
    for key, skills in ROLE_SKILLS.items():
        if key in role:
            for skill in skills:
                add(skill, f"Commonly expected for “{target_role.strip()}”")
            break
    for skill, reason in learned:
        add(skill, reason)
    return [{"skill": k, "reason": " · ".join(reasons[k])} for k in order[:10]]


# ------------------------------------------------------------------- the review
def _check(group, label, maximum, earned, detail="", advice=""):
    status = "na" if maximum is None else "pass" if earned >= maximum else "fail" if earned <= 0 else "partial"
    return {"group": group, "label": label, "max": maximum, "earned": round(earned or 0, 1), "status": status, "detail": detail, "advice": advice}


def analyze(text, job_description="", meta=None, target_role="", learned=()):
    meta = meta or {}
    text = text or ""
    words = re.findall(r"[A-Za-z0-9+#.'/-]+", text)
    found, nonstd, content = scan_sections(text)
    contact = contact_info(text)
    bullets = extract_bullets(text, content)
    checks = []

    # ---- Sections (30)
    G = "Sections and headings"
    for key, pts, why in (("summary", 4, "A 2 to 3 sentence summary tells the reader who you are."),
                          ("skills", 6, "A Skills section is the first place keyword scanners look."),
                          ("education", 6, "Education is expected on every student resume."),
                          ("experience", 4, "List internships or work, even short ones, under “Experience”."),
                          ("projects", 4, "Projects prove your skills when you have little experience.")):
        ok = key in found
        checks.append(_check(G, f"{SECTION_LABELS[key]} section", pts, pts if ok else 0,
                             "Found." if ok else "Not found.", "" if ok else f"Add a section headed “{SECTION_SYNONYMS[key][0].title()}”. {why}"))
    standard = len(found)
    if standard >= 3 and not nonstd:
        checks.append(_check(G, "Standard section headings", 6, 6, f"{standard} standard headings, no unusual ones."))
    else:
        earned = 3 if standard >= 3 else 0
        checks.append(_check(G, "Standard section headings", 6, earned,
                             (f"Unusual headings: {', '.join(nonstd)}. " if nonstd else "") + f"{standard} standard heading(s) found.",
                             "Use plain, common headings such as Education, Skills, Experience, Projects. Creative names can confuse parsers."))

    # ---- Contact (10)
    G = "Contact details"
    checks.append(_check(G, "Email address", 3, 3 if contact["email"] else 0, "Found." if contact["email"] else "Not found.", "" if contact["email"] else "Add a professional email address."))
    checks.append(_check(G, "Phone number", 3, 3 if contact["phone"] else 0, "Found." if contact["phone"] else "Not found.", "" if contact["phone"] else "Add a phone number with country code."))
    links = contact["linkedin"] or contact["github"] or contact["portfolio"]
    checks.append(_check(G, "LinkedIn, GitHub or portfolio link", 4, 4 if links else 0, "Found." if links else "Not found.",
                         "" if links else "Add your LinkedIn and/or GitHub address as plain text."))

    # ---- Formatting (15)
    G = "Formatting and readability"
    readable = len(text.strip()) >= 200
    checks.append(_check(G, "Text can be read from the file", 4, 4 if readable else 0, f"{len(text.strip())} characters of text found." ,
                         "" if readable else "Almost no text was found. A scanned or image-only resume cannot be read by software. Export a real text PDF."))
    n = len(words)
    length_pts = 4 if 250 <= n <= 900 else 2 if 150 <= n < 250 or 900 < n <= 1200 else 0
    checks.append(_check(G, "Sensible length", 4, length_pts, f"About {n} words.",
                         "" if length_pts == 4 else "Most student resumes work best at roughly 250 to 800 words on one page (two at most)."))
    pages = meta.get("pages")
    if pages is None:
        checks.append(_check(G, "Page count", None, 0, "Not known for this file type."))
    else:
        checks.append(_check(G, "Page count", 3, 3 if pages <= 2 else 1.5 if pages == 3 else 0, f"{pages} page(s).",
                             "" if pages <= 2 else "Keep it to one page (two at most) unless you have a lot of experience."))
    column_lines = sum(1 for ln in text.splitlines()[3:] if re.search(r"\S(?: {3,}|\t)\S", ln) or ln.count("|") >= 2)
    tabular = column_lines >= 3 or bool(meta.get("has_tables"))
    checks.append(_check(G, "No tables or multi-column layout", 2, 0 if tabular else 2,
                         "Table or column-like layout detected." if tabular else "Looks like a single column.",
                         "Use one column and no tables. Many parsers read tables and columns in the wrong order." if tabular else ""))
    decor = [c for c in text if (0x2190 <= ord(c) <= 0x2BFF and c not in ALLOWED_SYMBOLS) or ord(c) >= 0x1F000]
    checks.append(_check(G, "No icons, emoji or decorative symbols", 2, 0 if decor else 2,
                         f"Found: {' '.join(sorted(set(decor))[:8])}" if decor else "None found.",
                         "Remove icons and emoji (for example ☎ ✉ ★). Write plain words such as “Phone:”." if decor else ""))

    # ---- Bullets (20)
    G = "Achievement-oriented bullets"
    nb = len(bullets)
    if nb == 0:
        for label, pts in (("Bullet points describing your work", 4), ("Bullets start with action verbs", 6), ("Bullets include numbers or results", 6),
                           ("No weak phrases", 2), ("No first-person pronouns", 2)):
            checks.append(_check(G, label, pts, 0, "No bullets found.", "Add 2 to 4 bullets per project or internship, each describing what you did and the result."))
    else:
        verbs = [b for b in bullets if (m := re.match(r"[A-Za-z]+", b)) and (m.group(0).lower() in ACTION_VERBS or (m.group(0).lower().endswith("ed") and len(m.group(0)) > 4))]
        metrics = [b for b in bullets if re.search(r"\d", b)]
        weak = [p for p in WEAK_PHRASES if any(p in b.lower() for b in bullets)]
        first = [b for b in bullets if re.search(r"\b(I|my|me|myself)\b", b) or re.search(r"\b(my|myself)\b", b.lower())]
        count_pts = 4 if nb >= 3 else 2
        checks.append(_check(G, "Bullet points describing your work", 4, count_pts, f"{nb} bullet(s) found.", "" if nb >= 3 else "Aim for at least 3 bullets across your projects and experience."))
        vr, mr = len(verbs) / nb, len(metrics) / nb
        weak_verbs = [b for b in bullets if b not in verbs]
        checks.append(_check(G, "Bullets start with action verbs", 6, 6 * min(1, vr / 0.7), f"{len(verbs)} of {nb} start with an action verb.",
                             "" if vr >= 0.7 else "Start bullets with strong verbs such as Built, Designed, Improved, Automated. Examples to rewrite: " + " | ".join(b[:60] for b in weak_verbs[:2])))
        no_metric = [b for b in bullets if b not in metrics]
        checks.append(_check(G, "Bullets include numbers or results", 6, 6 * min(1, mr / 0.3), f"{len(metrics)} of {nb} include a number.",
                             "" if mr >= 0.3 else "Add measurable results (%, counts, time saved, users). Examples to improve: " + " | ".join(b[:60] for b in no_metric[:2])))
        checks.append(_check(G, "No weak phrases", 2, 2 if not weak else 1 if len(weak) == 1 else 0, "None found." if not weak else f"Found: {', '.join(weak)}.",
                             "" if not weak else "Replace phrases like “responsible for” or “worked on” with a direct action verb."))
        checks.append(_check(G, "No first-person pronouns", 2, 0 if first else 2, "None found." if not first else f"{len(first)} bullet(s) use I/my/me.",
                             "" if not first else "Remove “I” and “my”. Resume bullets are written without pronouns."))

    # ---- Writing (5)
    G = "Writing quality"
    issues = writing_issues(text, bullets)
    checks.append(_check(G, "Common writing mistakes", 5, max(0, 5 - len(issues)), "No issues found." if not issues else f"{len(issues)} kind(s) of issue found (see below).",
                         "" if not issues else "Fix the items listed under “Writing suggestions”. This is a basic check, not a full spell or grammar checker."))

    # ---- Keywords (20) only with a job description
    skills_jd, others = extract_keywords(job_description)
    keywords = {"provided": bool((job_description or "").strip()), "matched": [], "missing": [], "coverage": None, "other_words": others}
    if keywords["provided"]:
        pool = skills_jd + ([] if len(skills_jd) >= 3 else others[: 8 - len(skills_jd)])
        if pool:
            matched = [k for k in pool if has_keyword(text, k)]
            missing = [k for k in pool if k not in matched]
            cov = len(matched) / len(pool)
            keywords.update(matched=matched, missing=missing, coverage=round(100 * cov))
            checks.append(_check("Keywords from the job description", "Keyword coverage", 20, 20 * cov, f"{len(matched)} of {len(pool)} keywords found in your resume.",
                                 "" if not missing else "Add the missing keywords where they are TRUE for you, in Skills, Projects or bullets: " + ", ".join(missing[:10])))
        else:
            checks.append(_check("Keywords from the job description", "Keyword coverage", None, 0, "The job description had no recognisable skills.",
                                 "Paste a longer job description that lists tools and skills."))
    else:
        checks.append(_check("Keywords from the job description", "Keyword coverage", None, 0, "No job description given.", "Paste a job description to check keyword coverage."))
        keywords["missing"] = []

    # ---- totals
    possible = sum(c["max"] for c in checks if c["max"] is not None)
    earned = sum(c["earned"] for c in checks if c["max"] is not None)
    groups = []
    for name in dict.fromkeys(c["group"] for c in checks):
        items = [c for c in checks if c["group"] == name]
        groups.append({"name": name, "max": sum(c["max"] or 0 for c in items), "earned": round(sum(c["earned"] for c in items if c["max"] is not None), 1), "checks": items})
    return {
        "score": round(100 * earned / possible) if possible else 0, "earned": round(earned, 1), "possible": possible,
        "keyword_check_applied": keywords["provided"] and keywords["coverage"] is not None,
        "groups": groups, "missing_sections": [SECTION_LABELS[k] for k in ("summary", "skills", "education", "experience", "projects") if k not in found],
        "nonstandard_headings": nonstd, "keywords": keywords, "writing": issues,
        "skill_suggestions": skill_suggestions(text, keywords["missing"], target_role, learned),
        "stats": {"words": n, "bullets": nb, "pages": pages, "sections_found": sorted(found), "contact": contact},
        "disclaimer": DISCLAIMER,
    }
