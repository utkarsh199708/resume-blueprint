"""Text out of the files people have: PDF, Word (.docx), or plain text."""

from __future__ import annotations

import io
import re
import zipfile
from xml.etree import ElementTree

MAX_BYTES = 10 * 1024 * 1024


class UnreadableFile(ValueError):
    pass


def extract_text(data: bytes, filename: str = "") -> str:
    if len(data) > MAX_BYTES:
        raise UnreadableFile("File is larger than 10 MB.")
    name = filename.lower()
    if name.endswith(".pdf") or data[:5] == b"%PDF-":
        return _pdf(data)
    if name.endswith(".docx") or (data[:2] == b"PK" and b"word/" in data[:4000]):
        return _docx(data)
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise UnreadableFile("Could not read this file as text.")


def _pdf(data: bytes) -> str:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages[:20]]
    except Exception as exc:  # pypdf raises many types for damaged files
        raise UnreadableFile(f"Could not read this PDF ({exc.__class__.__name__}).") from exc
    text = "\n".join(pages)
    if not text.strip():
        raise UnreadableFile("This PDF has no text layer (it may be a scan). Paste the text "
                             "instead.")
    # PDF extraction splits bullets oddly: join a line that continues mid-sentence.
    text = re.sub(r"(?<=[a-z,])\n(?=[a-z])", " ", text)
    return text


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _docx(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            xml = z.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError) as exc:
        raise UnreadableFile("Could not read this Word file.") from exc
    root = ElementTree.fromstring(xml)
    paras = []
    for p in root.iter(f"{W}p"):
        texts = [t.text or "" for t in p.iter(f"{W}t")]
        is_list = p.find(f"{W}pPr/{W}numPr") is not None
        line = "".join(texts).strip()
        if line:
            paras.append(("• " if is_list else "") + line)
    return "\n".join(paras)
