"""A plain Word file from resume text: one column, real headings, no tables or text boxes.

Applicant tracking systems read simple single-column documents most reliably, so the file holds
nothing else: the name, a contact line, the headline, then each section under its own heading.
"""

from __future__ import annotations

import io
import zipfile
from xml.sax.saxutils import escape

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
CONTENT_TYPES = XML + (
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" '
    'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" ContentType="application/'
    'vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    '<Override PartName="/word/styles.xml" ContentType="application/'
    'vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
    '</Types>')
RELS = XML + (
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
    'relationships/officeDocument" Target="word/document.xml"/></Relationships>')
DOC_RELS = XML + (
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
    'relationships/styles" Target="styles.xml"/></Relationships>')
STYLES = XML + (
    f'<w:styles xmlns:w="{W}"><w:docDefaults><w:rPrDefault><w:rPr>'
    '<w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri" w:eastAsia="Calibri"/>'
    '<w:sz w:val="21"/><w:szCs w:val="21"/></w:rPr></w:rPrDefault>'
    '<w:pPrDefault><w:pPr><w:spacing w:after="60" w:line="264" w:lineRule="auto"/></w:pPr>'
    '</w:pPrDefault></w:docDefaults>'
    '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/>'
    '</w:style>'
    '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/>'
    '<w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/>'
    '<w:pBdr><w:bottom w:val="single" w:sz="4" w:space="1" w:color="999999"/></w:pBdr>'
    '<w:spacing w:before="220" w:after="80"/><w:outlineLvl w:val="0"/></w:pPr>'
    '<w:rPr><w:b/><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr></w:style>'
    '</w:styles>')


def _run(text: str, bold: bool = False, size: int | None = None) -> str:
    props = ("<w:b/>" if bold else "") + (f'<w:sz w:val="{size * 2}"/>' if size else "")
    rpr = f"<w:rPr>{props}</w:rPr>" if props else ""
    return f'<w:r>{rpr}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'


def _para(runs: list[str], style: str = "", bullet: bool = False, after: int | None = None) -> str:
    ppr = (f'<w:pStyle w:val="{style}"/>' if style else "") \
        + (f'<w:spacing w:after="{after}"/>' if after is not None else "") \
        + ('<w:ind w:left="284" w:hanging="284"/>' if bullet else "")
    return f"<w:p><w:pPr>{ppr}</w:pPr>{''.join(runs)}</w:p>"


def to_docx(text: str) -> bytes:
    """``text`` as made by ``ats.resume_text``: name, contact line, headline, then sections whose
    headings are in capitals."""
    body: list[str] = []
    seen = 0
    section = ""
    for raw in text.replace("\r", "").split("\n"):
        line = raw.strip()
        if not line:
            continue
        seen += 1
        if seen == 1:
            body.append(_para([_run(line, bold=True, size=18)], after=40))
        elif seen == 2:
            body.append(_para([_run(line, size=10)], after=120))
        elif seen == 3:
            body.append(_para([_run(line, bold=True, size=12)]))
        elif line.isupper() and len(line) <= 40:
            section = line
            body.append(_para([_run(line)], style="Heading1"))
        elif line.startswith("• "):
            body.append(_para([_run(line)], bullet=True))
        elif section == "SKILLS" and ": " in line:
            label, items = line.split(": ", 1)
            body.append(_para([_run(f"{label}: ", bold=True), _run(items)]))
        else:
            body.append(_para([_run(line)]))
    document = XML + (
        f'<w:document xmlns:w="{W}"><w:body>{"".join(body)}'
        '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1008" w:right="1008" '
        'w:bottom="1008" w:left="1008" w:header="720" w:footer="720" w:gutter="0"/>'
        '</w:sectPr></w:body></w:document>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", RELS)
        z.writestr("word/_rels/document.xml.rels", DOC_RELS)
        z.writestr("word/styles.xml", STYLES)
        z.writestr("word/document.xml", document)
    return buf.getvalue()
