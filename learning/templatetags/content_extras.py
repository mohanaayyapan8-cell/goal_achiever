from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def rich_text(value):
    """Safe mini-formatter for lesson text.
    Everything is HTML-escaped FIRST; then lines starting with '- ' become bullets
    and blank lines separate paragraphs. No raw HTML from the text ever reaches the page."""
    if not value:
        return ""
    html, bullets, para = [], [], []

    def flush():
        if bullets:
            html.append("<ul>" + "".join(f"<li>{b}</li>" for b in bullets) + "</ul>")
            bullets.clear()
        if para:
            html.append("<p>" + "<br>".join(para) + "</p>")
            para.clear()

    for line in str(value).splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            if para:
                flush()
            bullets.append(escape(stripped[2:]))
        elif not stripped:
            flush()
        else:
            if bullets:
                flush()
            para.append(escape(stripped))
    flush()
    return mark_safe("".join(html))
