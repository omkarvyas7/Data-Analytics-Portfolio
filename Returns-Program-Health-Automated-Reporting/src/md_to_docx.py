"""Minimal Markdown -> .docx converter (headings, paragraphs, bullets, numbered lists, pipe tables, **bold**)."""
import re

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor


def _runs(par, text):
    parts = re.split(r"(\*\*[^*]+\*\*|`[^`]+`)", text)
    for p in parts:
        if not p:
            continue
        if p.startswith("**") and p.endswith("**"):
            par.add_run(p[2:-2]).bold = True
        elif p.startswith("`") and p.endswith("`"):
            r = par.add_run(p[1:-1])
            r.font.name = "Consolas"
            r.font.size = Pt(9)
        else:
            par.add_run(p)


def _table(doc, rows):
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    cells = [r for r in cells if not all(re.fullmatch(r":?-{2,}:?", c) for c in r)]
    ncol = max(len(r) for r in cells)
    t = doc.add_table(rows=len(cells), cols=ncol)
    t.style = "Light Grid Accent 1"
    for i, r in enumerate(cells):
        for j in range(ncol):
            cell = t.cell(i, j)
            cell.text = ""
            p = cell.paragraphs[0]
            _runs(p, r[j] if j < len(r) else "")
            for run in p.runs:
                run.font.size = Pt(8.5)
                if i == 0:
                    run.bold = True
    doc.add_paragraph()


def convert(md_text, out_path, title=None):
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(10.5)
    lines = md_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if s.startswith("|"):
            block = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                block.append(lines[i])
                i += 1
            _table(doc, block)
            continue
        if not s:
            i += 1
            continue
        m = re.match(r"^(#{1,4})\s+(.*)", s)
        if m:
            level = len(m.group(1))
            h = doc.add_heading(m.group(2), level=0 if level == 1 else level - 1)
            if level == 1:
                h.alignment = WD_ALIGN_PARAGRAPH.LEFT
            for r in h.runs:
                r.font.color.rgb = RGBColor(0x23, 0x2F, 0x3E)
        elif re.match(r"^[-*]\s+", s):
            indent = len(line) - len(line.lstrip())
            p = doc.add_paragraph(style="List Bullet 2" if indent >= 2 else "List Bullet")
            _runs(p, re.sub(r"^[-*]\s+", "", s))
        elif re.match(r"^\d+\.\s+", s):
            p = doc.add_paragraph(style="List Number")
            _runs(p, re.sub(r"^\d+\.\s+", "", s))
        elif s.startswith(">"):
            p = doc.add_paragraph()
            _runs(p, s.lstrip("> "))
            p.paragraph_format.left_indent = Pt(18)
            for r in p.runs:
                r.italic = True
        elif s.startswith("```"):
            i += 1
            buf = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            p = doc.add_paragraph()
            r = p.add_run("\n".join(buf))
            r.font.name = "Consolas"
            r.font.size = Pt(8.5)
        else:
            p = doc.add_paragraph()
            _runs(p, s)
        i += 1
    if title:
        doc.core_properties.title = title
    doc.core_properties.author = "Omkar Vyas"
    doc.save(out_path)
