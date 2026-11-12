"""Minimal dependency-free DOCX (OOXML) writer for MLR reports and bundle proposals.

Supports headings, paragraphs with bold/italic/colored runs, bullet-style lines and simple bordered tables.
"""
from __future__ import annotations

import io
import zipfile
from datetime import datetime, timezone
from typing import List, Optional, Sequence, Tuple, Union
from xml.sax.saxutils import escape

Run = Union[str, Tuple[str, dict]]

_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
</Types>"""
_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
</Relationships>"""
_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _strip_invalid(text: str) -> str:
    return "".join(ch for ch in text if ch in "\t\n\r" or ord(ch) >= 0x20)


class DocxBuilder:
    def __init__(self, title: str, author: str = "J&J GraphRAG Nexus"):
        self.title = title
        self.author = author
        self.body: List[str] = []

    @staticmethod
    def _run(text: str, bold: bool = False, italic: bool = False, color: Optional[str] = None, size: Optional[int] = None,
             highlight: Optional[str] = None) -> str:
        props = ""
        if bold:
            props += "<w:b/>"
        if italic:
            props += "<w:i/>"
        if color:
            props += f'<w:color w:val="{color}"/>'
        if size:
            props += f'<w:sz w:val="{size * 2}"/>'
        if highlight:
            props += f'<w:highlight w:val="{highlight}"/>'
        rpr = f"<w:rPr>{props}</w:rPr>" if props else ""
        return f'<w:r>{rpr}<w:t xml:space="preserve">{escape(_strip_invalid(text))}</w:t></w:r>'

    def _runs(self, runs: Sequence[Run]) -> str:
        out = []
        for r in runs:
            if isinstance(r, str):
                out.append(self._run(r))
            else:
                out.append(self._run(r[0], **r[1]))
        return "".join(out)

    def heading(self, text: str, level: int = 1) -> "DocxBuilder":
        size = {0: 20, 1: 16, 2: 13, 3: 12}.get(level, 12)
        self.body.append(f'<w:p><w:pPr><w:spacing w:before="240" w:after="120"/></w:pPr>{self._run(text, bold=True, size=size, color="C8102E" if level <= 1 else "1F2937")}</w:p>')
        return self

    def paragraph(self, *runs: Run, indent: int = 0) -> "DocxBuilder":
        ind = f'<w:ind w:left="{indent * 360}"/>' if indent else ""
        self.body.append(f'<w:p><w:pPr><w:spacing w:after="80"/>{ind}</w:pPr>{self._runs(runs)}</w:p>')
        return self

    def bullet(self, *runs: Run, level: int = 0) -> "DocxBuilder":
        return self.paragraph("\u2022 ", *runs, indent=level + 1)

    def table(self, header: Sequence[str], rows: Sequence[Sequence[str]], widths: Optional[Sequence[int]] = None) -> "DocxBuilder":
        n = len(header)
        widths = list(widths or [int(9000 / n)] * n)
        border = "".join(f'<w:{b} w:val="single" w:sz="4" w:space="0" w:color="9CA3AF"/>' for b in ("top", "left", "bottom", "right", "insideH", "insideV"))
        grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in widths)

        def cell(text: str, w: int, head: bool) -> str:
            shade = '<w:shd w:val="clear" w:color="auto" w:fill="F3F4F6"/>' if head else ""
            paras = "".join(f"<w:p>{self._run(line, bold=head, size=9)}</w:p>" for line in (str(text) or " ").split("\n"))
            return f'<w:tc><w:tcPr><w:tcW w:w="{w}" w:type="dxa"/>{shade}</w:tcPr>{paras}</w:tc>'

        xml = [f'<w:tbl><w:tblPr><w:tblW w:w="0" w:type="auto"/><w:tblBorders>{border}</w:tblBorders></w:tblPr><w:tblGrid>{grid}</w:tblGrid>']
        xml.append("<w:tr>" + "".join(cell(h, w, True) for h, w in zip(header, widths)) + "</w:tr>")
        for row in rows:
            xml.append("<w:tr>" + "".join(cell(c, w, False) for c, w in zip(row, widths)) + "</w:tr>")
        xml.append("</w:tbl>")
        self.body.append("".join(xml))
        self.body.append("<w:p/>")
        return self

    def to_bytes(self) -> bytes:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        document = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="{_W}"><w:body>'
                    + "".join(self.body)
                    + '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1080" w:right="1080" w:bottom="1080" w:left="1080" '
                      'w:header="720" w:footer="720" w:gutter="0"/></w:sectPr></w:body></w:document>')
        core = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties '
                'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" '
                'xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
                f"<dc:title>{escape(self.title)}</dc:title><dc:creator>{escape(self.author)}</dc:creator>"
                f'<dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created></cp:coreProperties>')
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", _CONTENT_TYPES)
            z.writestr("_rels/.rels", _RELS)
            z.writestr("word/document.xml", document)
            z.writestr("docProps/core.xml", core)
        return buf.getvalue()


DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
