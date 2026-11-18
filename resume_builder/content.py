"""One place that turns a Resume into display content. The HTML preview, the PDF and the plain-text
version (used for the ATS review) all come from here, so they always match."""
import re

BULLET_CHARS = "•·▪●◦*-–—▸►"
SECTION_ORDER = {
    "student": ["education", "skills", "projects", "experience", "certifications", "achievements"],
    "professional": ["skills", "experience", "projects", "education", "certifications", "achievements"],
}
TITLES = {"summary": "Summary", "skills": "Skills", "experience": "Experience", "projects": "Projects",
          "education": "Education", "certifications": "Certifications", "achievements": "Achievements"}


def bullets_list(text):
    """One bullet per non-empty line; leading bullet symbols are removed."""
    out = []
    for line in (text or "").splitlines():
        line = line.strip().lstrip(BULLET_CHARS + " ").strip()
        if line:
            out.append(line)
    return out


def skill_lines(text):
    return [ln.strip() for ln in (text or "").splitlines() if ln.strip()]


def _short_url(url):
    return re.sub(r"^https?://(www\.)?", "", url or "").rstrip("/")


def _dates(start, end):
    return " – ".join(x for x in (start, end) if x)


def resume_content(resume):
    """Structured content: {"name", "headline", "contact": [..], "sections": [{"key","title","items": [...]}]}"""
    contact = [x for x in (resume.email, resume.phone, resume.location, _short_url(resume.linkedin_url),
                           _short_url(resume.github_url), _short_url(resume.portfolio_url)) if x]
    items = {
        "summary": [{"text": resume.summary.strip()}] if resume.summary.strip() else [],
        "skills": [{"text": ln} for ln in skill_lines(resume.skills)],
        "education": [{"title": e.institution, "subtitle": e.degree, "dates": _dates(e.start, e.end), "extra": e.grade and f"CGPA/Score: {e.grade}",
                       "bullets": bullets_list(e.bullets)} for e in resume.educations.all()],
        "experience": [{"title": x.role, "subtitle": ", ".join(p for p in (x.organization, x.location) if p), "dates": _dates(x.start, x.end),
                        "bullets": bullets_list(x.bullets)} for x in resume.experiences.all()],
        "projects": [{"title": p.name, "subtitle": p.tech_stack and f"Technologies: {p.tech_stack}", "dates": "",
                      "extra": _short_url(p.link), "bullets": bullets_list(p.bullets)} for p in resume.projects.all()],
        "certifications": [{"text": " – ".join(x for x in (c.name, c.issuer, c.year) if x)} for c in resume.certifications.all()],
        "achievements": [{"text": a.text} for a in resume.achievements.all()],
    }
    order = ["summary"] + SECTION_ORDER.get(resume.layout, SECTION_ORDER["student"])
    return {"name": resume.full_name, "headline": resume.headline, "contact": contact,
            "sections": [{"key": k, "title": TITLES[k], "items": items[k]} for k in order if items[k]]}


def resume_to_text(resume):
    """Plain text, exactly the words the PDF contains. Used by the ATS review."""
    c = resume_content(resume)
    lines = [c["name"]] + ([c["headline"]] if c["headline"] else []) + ([" | ".join(c["contact"])] if c["contact"] else [])
    for sec in c["sections"]:
        lines += ["", sec["title"]]
        for item in sec["items"]:
            if "text" in item:
                lines.append(item["text"] if sec["key"] in ("summary", "skills") else f"- {item['text']}")
                continue
            head = " | ".join(x for x in (item.get("title"), item.get("subtitle"), item.get("dates"), item.get("extra")) if x)
            lines.append(head)
            lines += [f"- {b}" for b in item["bullets"]]
    return "\n".join(lines).strip() + "\n"


def completeness(resume):
    """(percent, [what is still missing]) to guide the user while building."""
    skills = [s for line in skill_lines(resume.skills) for s in re.split(r"[,;]", line.split(":", 1)[-1]) if s.strip()]
    checks = [
        (bool(resume.full_name.strip()), "your name"), (bool(resume.email), "an email address"), (bool(resume.phone), "a phone number"),
        (len(resume.summary.split()) >= 20, "a summary of about 2 to 3 sentences"), (len(skills) >= 5, "at least 5 skills"),
        (resume.educations.exists(), "your education"), (resume.projects.exists() or resume.experiences.exists(), "a project or an internship"),
        (resume.projects.count() + resume.experiences.count() >= 2, "two or more projects/internships"),
        (bool(resume.linkedin_url or resume.github_url), "a LinkedIn or GitHub link"),
    ]
    missing = [label for ok, label in checks if not ok]
    return round(100 * (len(checks) - len(missing)) / len(checks)), missing
