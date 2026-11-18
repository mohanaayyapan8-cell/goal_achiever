"""PDF export with reportlab. Built for applicant-tracking systems: one column, real selectable text,
standard section names, standard fonts, no tables, no images, no icons."""
import io
from xml.sax.saxutils import escape

from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer

from .content import resume_content

_REPLACEMENTS = {"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-", "\u2014": "-", "\u2026": "...",
                 "\u00a0": " ", "\u2022": "\u2022", "\t": " "}


def pdf_safe(text):
    """Make text printable with the standard PDF font. Returns (clean_text, sorted unsupported characters)."""
    out, bad = [], set()
    for ch in text or "":
        ch = _REPLACEMENTS.get(ch, ch)
        try:
            ch.encode("cp1252")
            out.append(ch)
        except UnicodeEncodeError:
            bad.add(ch)
            out.append("?")
    return "".join(out), sorted(bad)


def unsupported_characters(resume):
    """Characters in the resume that the PDF font cannot show (so the user can fix them first)."""
    c = resume_content(resume)
    parts = [c["name"], c["headline"], *c["contact"]]
    for sec in c["sections"]:
        for item in sec["items"]:
            parts += [str(v) for k, v in item.items() if k != "bullets" and v] + item.get("bullets", [])
    return pdf_safe("\n".join(parts))[1]


def build_pdf(resume):
    c = resume_content(resume)
    base = ParagraphStyle("base", fontName="Helvetica", fontSize=10, leading=13)
    name = ParagraphStyle("name", parent=base, fontName="Helvetica-Bold", fontSize=18, leading=22, alignment=TA_CENTER)
    center = ParagraphStyle("center", parent=base, alignment=TA_CENTER)
    heading = ParagraphStyle("heading", parent=base, fontName="Helvetica-Bold", fontSize=11, leading=14, spaceBefore=9, spaceAfter=3)
    bullet = ParagraphStyle("bullet", parent=base, leftIndent=12, bulletIndent=2)

    def P(text, style, **kw):
        return Paragraph(escape(pdf_safe(text)[0]), style, **kw)

    story = [P(c["name"], name)]
    if c["headline"]:
        story.append(P(c["headline"], center))
    if c["contact"]:
        story.append(P(" | ".join(c["contact"]), center))
    for sec in c["sections"]:
        block = [P(sec["title"].upper(), heading)]
        for item in sec["items"]:
            if "text" in item:
                block.append(P(item["text"], bullet, bulletText="\u2022") if sec["key"] in ("certifications", "achievements") else P(item["text"], base))
                continue
            head = Paragraph(f"<b>{escape(pdf_safe(item['title'])[0])}</b>" + (f" - {escape(pdf_safe(item['subtitle'])[0])}" if item.get("subtitle") else "")
                             + (f" ({escape(pdf_safe(item['dates'])[0])})" if item.get("dates") else ""), base)
            lines = [head] + ([P(item["extra"], base)] if item.get("extra") else []) + [P(b, bullet, bulletText="\u2022") for b in item["bullets"]]
            block.append(KeepTogether(lines[:3]))
            block += lines[3:]
            block.append(Spacer(1, 2))
        story += block
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=15 * mm, bottomMargin=15 * mm,
                            title=pdf_safe(f"{c['name']} - Resume")[0], author=pdf_safe(c["name"])[0], subject="Resume")
    doc.build(story)
    return buffer.getvalue()
