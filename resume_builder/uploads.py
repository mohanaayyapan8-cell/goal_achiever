"""Safe handling of uploaded resume files: strict checks BEFORE saving, and text extraction.
Nothing from an uploaded file is ever executed or served publicly."""
import io
import zipfile

from django.conf import settings
from django.core.exceptions import ValidationError

MAX_PAGES = 10
MAX_CHARS = 100_000
MAX_ZIP_ENTRIES, MAX_ZIP_UNCOMPRESSED = 2000, 30 * 1024 * 1024
ALLOWED = {"pdf", "docx", "txt"}


class ExtractionError(Exception):
    pass


def detect_kind(name, data):
    """Check extension AND content. Returns 'pdf', 'docx' or 'txt', or raises ValidationError."""
    ext = (name.rsplit(".", 1)[-1] if "." in name else "").lower()
    if ext == "doc":
        raise ValidationError("Old .doc files are not supported. Please save the resume as PDF or DOCX.")
    if ext not in ALLOWED:
        raise ValidationError("Please upload a PDF, DOCX or TXT file.")
    if not data:
        raise ValidationError("The file is empty.")
    if ext == "pdf":
        if not data.startswith(b"%PDF-"):
            raise ValidationError("This file is not a real PDF.")
    elif ext == "docx":
        if not data.startswith(b"PK\x03\x04"):
            raise ValidationError("This file is not a real DOCX document.")
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                infos = z.infolist()
                if len(infos) > MAX_ZIP_ENTRIES or sum(i.file_size for i in infos) > MAX_ZIP_UNCOMPRESSED:
                    raise ValidationError("This document is too large or complex to review.")
                if "word/document.xml" not in z.namelist():
                    raise ValidationError("This file is not a real DOCX document.")
        except zipfile.BadZipFile:
            raise ValidationError("This file is not a real DOCX document.")
    else:
        if b"\x00" in data[:4096]:
            raise ValidationError("This does not look like a plain text file.")
    return ext


def validate_upload(uploaded):
    """Returns (kind, bytes). Raises ValidationError with a friendly message."""
    limit = settings.RESUME_MAX_UPLOAD_BYTES
    if uploaded.size > limit:
        raise ValidationError(f"The file is too large. The limit is {limit // (1024 * 1024)} MB.")
    data = uploaded.read(limit + 1)
    if len(data) > limit:
        raise ValidationError(f"The file is too large. The limit is {limit // (1024 * 1024)} MB.")
    return detect_kind(uploaded.name or "", data), data


def extract_text(kind, data):
    """Returns {"text", "pages", "has_tables", "pages_read"}. Raises ExtractionError with a friendly message."""
    try:
        if kind == "pdf":
            return _pdf(data)
        if kind == "docx":
            return _docx(data)
        return {"text": data.decode("utf-8", errors="replace")[:MAX_CHARS], "pages": None, "has_tables": False}
    except ExtractionError:
        raise
    except Exception as exc:                                    # damaged or unusual files must never crash the page
        raise ExtractionError("This file could not be read. Try saving it again as a PDF or DOCX.") from exc


def _pdf(data):
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data), strict=False)
    if reader.is_encrypted:
        try:
            if not reader.decrypt(""):
                raise ExtractionError("This PDF is password protected. Please upload an unprotected copy.")
        except ExtractionError:
            raise
        except Exception:
            raise ExtractionError("This PDF is password protected. Please upload an unprotected copy.")
    total = len(reader.pages)
    text = "\n".join((page.extract_text() or "") for page in reader.pages[:MAX_PAGES])
    return {"text": text[:MAX_CHARS], "pages": total, "has_tables": False}


def _docx(data):
    from docx import Document
    doc = Document(io.BytesIO(data))
    parts = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            parts += [cell.text for cell in row.cells]
    return {"text": "\n".join(parts)[:MAX_CHARS], "pages": None, "has_tables": bool(doc.tables)}
