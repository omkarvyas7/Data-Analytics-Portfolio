"""Minimal markdown -> .docx (python-docx) and -> .pdf (reportlab) renderer for the project docs.

Supports: # headings (1-4), paragraphs, '- ' bullets, '1. ' numbered items, pipe tables,
images ![alt](relative/path.png), **bold** and `code` inline. That covers what the project docs use.
"""
from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.shared import Inches, Pt, RGBColor
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (Image, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

IMG_RE = re.compile(r"^!\[(.*?)\]\((.*?)\)\s*$")
NUM_RE = re.compile(r"^(\d+)\.\s+(.*)")


def parse(md: str) -> list[tuple]:
    """Return blocks: ('h', level, text) | ('p', text) | ('ul', [items]) | ('ol', [items]) |
    ('table', rows) | ('img', alt, path)."""
    blocks: list[tuple] = []
    lines = md.splitlines()
    i = 0
    para: list[str] = []

    def flush():
        if para:
            blocks.append(("p", " ".join(s.strip() for s in para)))
            para.clear()

    while i < len(lines):
        ln = lines[i].rstrip()
        if not ln.strip():
            flush()
            i += 1
            continue
        if ln.startswith("#"):
            flush()
            lvl = len(ln) - len(ln.lstrip("#"))
            blocks.append(("h", lvl, ln[lvl:].strip()))
            i += 1
            continue
        mimg = IMG_RE.match(ln.strip())
        if mimg:
            flush()
            blocks.append(("img", mimg.group(1), mimg.group(2)))
            i += 1
            continue
        if ln.lstrip().startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            blocks.append(("table", rows))
            continue
        if ln.lstrip().startswith("- "):
            flush()
            items = []
            while i < len(lines) and lines[i].lstrip().startswith("- "):
                items.append(lines[i].lstrip()[2:].strip())
                i += 1
            blocks.append(("ul", items))
            continue
        if NUM_RE.match(ln.lstrip()):
            flush()
            items = []
            while i < len(lines) and NUM_RE.match(lines[i].lstrip()):
                items.append(NUM_RE.match(lines[i].lstrip()).group(2))
                i += 1
            blocks.append(("ol", items))
            continue
        para.append(ln)
        i += 1
    flush()
    return blocks


def _runs(par, text: str) -> None:
    for part in re.split(r"(\*\*.+?\*\*|`.+?`)", text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            par.add_run(part[2:-2]).bold = True
        elif part.startswith("`") and part.endswith("`"):
            r = par.add_run(part[1:-1])
            r.font.name = "Consolas"
            r.font.size = Pt(9)
        else:
            par.add_run(part)


def to_docx(md: str, out: Path, base_dir: Path) -> None:
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(10.5)
    for sec in doc.sections:
        sec.left_margin = sec.right_margin = Inches(0.9)
    for b in parse(md):
        kind = b[0]
        if kind == "h":
            h = doc.add_heading(level=min(b[1] - 1, 4) if b[1] > 1 else 0)
            _runs(h, b[2])
            for r in h.runs:
                r.font.color.rgb = RGBColor(0x1F, 0x3B, 0x57)
        elif kind == "p":
            _runs(doc.add_paragraph(), b[1])
        elif kind in ("ul", "ol"):
            for it in b[1]:
                _runs(doc.add_paragraph(style="List Bullet" if kind == "ul" else "List Number"), it)
        elif kind == "table":
            rows = b[1]
            ncol = max(len(r) for r in rows)
            t = doc.add_table(rows=len(rows), cols=ncol)
            t.style = "Light Grid Accent 1"
            t.alignment = WD_TABLE_ALIGNMENT.CENTER
            for ri, r in enumerate(rows):
                for ci in range(ncol):
                    cell = t.cell(ri, ci)
                    cell.text = ""
                    p = cell.paragraphs[0]
                    _runs(p, r[ci] if ci < len(r) else "")
                    for run in p.runs:
                        run.font.size = Pt(9)
                        if ri == 0:
                            run.bold = True
            doc.add_paragraph()
        elif kind == "img":
            p = base_dir / b[2]
            if p.exists():
                doc.add_picture(str(p), width=Inches(6.5))
                cap = doc.add_paragraph(b[1])
                cap.runs[0].italic = True
    doc.save(out)


def _rl(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`(.+?)`", r"<font face='Courier'>\1</font>", text)
    return text


def to_pdf(md: str, out: Path, base_dir: Path, title: str) -> None:
    ss = getSampleStyleSheet()
    navy = colors.HexColor("#1F3B57")
    styles = {
        1: ParagraphStyle("h1", parent=ss["Title"], textColor=navy, fontSize=18, spaceAfter=10, alignment=TA_LEFT),
        2: ParagraphStyle("h2", parent=ss["Heading2"], textColor=navy, fontSize=14, spaceBefore=10),
        3: ParagraphStyle("h3", parent=ss["Heading3"], textColor=navy, fontSize=11.5, spaceBefore=6),
        4: ParagraphStyle("h4", parent=ss["Heading4"], textColor=navy, fontSize=10.5),
    }
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=9.5, leading=13)
    cell = ParagraphStyle("c", parent=body, fontSize=8, leading=10)
    story = []
    width = letter[0] - 1.6 * inch
    for b in parse(md):
        kind = b[0]
        if kind == "h":
            story.append(Paragraph(_rl(b[2]), styles[min(b[1], 4)]))
        elif kind == "p":
            story.append(Paragraph(_rl(b[1]), body))
            story.append(Spacer(1, 4))
        elif kind in ("ul", "ol"):
            items = [ListItem(Paragraph(_rl(t), body), leftIndent=12) for t in b[1]]
            story.append(ListFlowable(items, bulletType="bullet" if kind == "ul" else "1", start=None if kind == "ul" else 1,
                                      leftIndent=14, bulletFontSize=8))
            story.append(Spacer(1, 4))
        elif kind == "table":
            rows = b[1]
            ncol = max(len(r) for r in rows)
            data = [[Paragraph(_rl(r[c] if c < len(r) else ""), cell) for c in range(ncol)] for r in rows]
            t = Table(data, colWidths=[width / ncol] * ncol, repeatRows=1)
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DCE6F0")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9AA5B1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
            story.append(t)
            story.append(Spacer(1, 8))
        elif kind == "img":
            p = base_dir / b[2]
            if p.exists():
                from PIL import Image as PILImage  # pillow ships with matplotlib
                w, h = PILImage.open(p).size
                story.append(Image(str(p), width=width, height=width * h / w))
                story.append(Paragraph(f"<i>{_rl(b[1])}</i>", cell))
                story.append(Spacer(1, 8))

    def footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.grey)
        canvas.drawString(0.8 * inch, 0.5 * inch, f"{title} (synthetic data, no Amazon or employer data used)")
        canvas.drawRightString(letter[0] - 0.8 * inch, 0.5 * inch, f"Page {doc_.page}")
        canvas.restoreState()

    SimpleDocTemplate(str(out), pagesize=letter, leftMargin=0.8 * inch, rightMargin=0.8 * inch,
                      topMargin=0.7 * inch, bottomMargin=0.8 * inch, title=title,
                      author="Omkar Vyas").build(story, onFirstPage=footer, onLaterPages=footer)
