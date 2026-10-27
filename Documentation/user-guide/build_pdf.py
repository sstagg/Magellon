"""Build the Magellon user guide PDF from guide.md and the pictures in images/.

    python build_pdf.py [guide.md] [output.pdf]

guide.md is ordinary Markdown with a few conventions (see README.md):
  - front matter (title, subtitle, lead, footer) for the cover page;
  - [[toc]] where the table of contents goes;
  - every "# " heading starts a new page;
  - "> **Tip.** ..." and "> **Important.** ..." become coloured boxes;
  - <!-- widths: 0.3 0.7 --> before a table sets its column widths
    (add "noheader" when the first row is not a header);
  - ![caption](images/x.jpg "crop=x0,y0,x1,y1 width=0.7") crops a picture
    and sets its width as a fraction of the text width.
"""
import os
import re
import sys

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "guide.md")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "Magellon-User-Guide.pdf")
CROPS = os.path.join(HERE, ".build")
os.makedirs(CROPS, exist_ok=True)

INK = colors.HexColor("#1b2430")
MUTED = colors.HexColor("#5b6675")
ACCENT = colors.HexColor("#0e7c86")
RULE = colors.HexColor("#d5dbe1")
TIP_BG = colors.HexColor("#e8f5f6")
WARN_BG = colors.HexColor("#fdf3e3")
WARN_EDGE = colors.HexColor("#d08a1c")

ss = getSampleStyleSheet()
BODY = ParagraphStyle("body", parent=ss["Normal"], fontName="Helvetica", fontSize=10, leading=14.5,
                      textColor=INK, spaceAfter=6)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=8.5, leading=11.5, textColor=MUTED)
CAP = ParagraphStyle("cap", parent=SMALL, alignment=TA_CENTER, spaceBefore=3, spaceAfter=12)
H1 = ParagraphStyle("h1", parent=BODY, fontName="Helvetica-Bold", fontSize=19, leading=24,
                    textColor=INK, spaceBefore=4, spaceAfter=10)
H2 = ParagraphStyle("h2", parent=BODY, fontName="Helvetica-Bold", fontSize=12.5, leading=16,
                    textColor=ACCENT, spaceBefore=10, spaceAfter=5)
BUL = ParagraphStyle("bul", parent=BODY, leftIndent=14, bulletIndent=3, spaceAfter=3)
CELL = ParagraphStyle("cell", parent=BODY, fontSize=9, leading=12, spaceAfter=0)
CELLB = ParagraphStyle("cellb", parent=CELL, fontName="Helvetica-Bold")

WIDTH = letter[0] - 2 * 0.85 * inch
story = []
meta = {}


class Doc(SimpleDocTemplate):
    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name in ("h1", "h2"):
            level = 0 if flowable.style.name == "h1" else 1
            key = "h%d" % id(flowable)
            self.canv.bookmarkPage(key)
            self.notify("TOCEntry", (level, flowable.getPlainText(), self.page, key))


def page_frame(canvas, doc):
    canvas.saveState()
    if doc.page > 1:
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(0.85 * inch, 0.55 * inch, meta.get("footer", ""))
        canvas.drawRightString(letter[0] - 0.85 * inch, 0.55 * inch, "Page %d" % doc.page)
        canvas.setStrokeColor(RULE)
        canvas.line(0.85 * inch, 0.72 * inch, letter[0] - 0.85 * inch, 0.72 * inch)
    canvas.restoreState()


def inline(text):
    """Markdown inline markup to reportlab's paragraph markup."""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    return text.replace("\\|", "|")


def box(text):
    warn = text.startswith("**Important.**")
    bg, edge = (WARN_BG, WARN_EDGE) if warn else (TIP_BG, ACCENT)
    t = Table([[Paragraph(inline(text), CELL)]], colWidths=[WIDTH])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), bg),
                           ("LINEBEFORE", (0, 0), (0, -1), 3, edge),
                           ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                           ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    story.append(t)
    story.append(Spacer(1, 8))


def table(rows, widths, header=True):
    if not widths:
        widths = [1.0 / len(rows[0])] * len(rows[0])
    data = [[Paragraph(inline(c), CELLB if (header and r == 0) else CELL) for c in row]
            for r, row in enumerate(rows)]
    t = Table(data, colWidths=[w * WIDTH for w in widths], repeatRows=1 if header else 0)
    style = [("GRID", (0, 0), (-1, -1), 0.5, RULE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
             ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef1f4")))
    t.setStyle(TableStyle(style))
    story.append(t)
    story.append(Spacer(1, 10))


def picture(path, caption, opts):
    """Add a screenshot. crop = x0,y0,x1,y1 in the coordinates of the picture
    scaled to 2000 px wide, so it holds whatever size the picture is saved at."""
    src = os.path.join(os.path.dirname(SRC), path)
    if not os.path.exists(src):
        print("missing picture", path)
        return
    img = PILImage.open(src).convert("RGB")
    crop = opts.get("crop")
    if crop:
        k = img.width / 2000.0
        img = img.crop(tuple(int(int(v) * k) for v in crop.split(",")))
    if img.width > 1800:
        img = img.resize((1800, int(img.height * 1800 / img.width)), PILImage.LANCZOS)
    out = os.path.join(CROPS, "%s_%s.jpg" % (os.path.basename(path).rsplit(".", 1)[0],
                                             crop.replace(",", "_") if crop else "full"))
    img.save(out, "JPEG", quality=82)
    w = WIDTH * float(opts.get("width", 1.0))
    h = w * img.height / img.width
    max_h = 6.3 * inch
    if h > max_h:
        w, h = w * max_h / h, max_h
    framed = Table([[Image(out, width=w, height=h)]], colWidths=[w + 2])
    framed.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, RULE),
                                ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    story.append(KeepTogether([framed, Paragraph(inline(caption), CAP)]))


def cover():
    story.append(Spacer(1, 1.6 * inch))
    story.append(Paragraph(inline(meta.get("title", "")),
                           ParagraphStyle("t", parent=H1, fontSize=40, leading=46, textColor=ACCENT)))
    story.append(Paragraph(inline(meta.get("subtitle", "")), ParagraphStyle("st", parent=H1, fontSize=20, leading=26)))
    story.append(Spacer(1, 14))
    story.append(Paragraph(inline(meta.get("lead", "")), ParagraphStyle("lead", parent=BODY, fontSize=12, leading=17)))
    story.append(Spacer(1, 30))


def contents():
    toc = TableOfContents()
    toc.levelStyles = [ParagraphStyle("toc0", parent=BODY, fontName="Helvetica-Bold", fontSize=10, leading=13,
                                      spaceBefore=3, spaceAfter=0),
                       ParagraphStyle("toc1", parent=BODY, fontSize=8.5, leading=10.5, leftIndent=14, spaceAfter=0)]
    story.append(PageBreak())
    story.append(Paragraph("Contents", H1.clone("tochead")))
    story.append(toc)


def split_row(line):
    s = line.strip()[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    return [c.strip() for c in re.split(r"(?<!\\)\|", s)]


def parse(text):
    lines = text.splitlines()
    i = 0
    if lines and lines[0].strip() == "---":
        i = 1
        while lines[i].strip() != "---":
            key, _, value = lines[i].partition(":")
            meta[key.strip()] = value.strip()
            i += 1
        i += 1
    cover()
    widths, header = None, True
    para = []

    def flush():
        if para:
            story.append(Paragraph(inline(" ".join(para)), BODY))
            para.clear()

    while i < len(lines):
        line = lines[i].rstrip()
        s = line.strip()
        m = re.match(r"<!--\s*widths:(.*)-->", s)
        if not s:
            flush()
        elif m:
            flush()
            words = m.group(1).split()
            header = "noheader" not in words
            widths = [float(w) for w in words if w != "noheader"]
        elif s.startswith("<!--"):
            flush()
        elif s == "[[toc]]":
            flush()
            contents()
        elif s.startswith("# "):
            flush()
            story.append(PageBreak())
            story.append(Paragraph(inline(s[2:]), H1))
        elif s.startswith("## "):
            flush()
            story.append(Paragraph(inline(s[3:]), H2))
        elif s.startswith("> "):
            flush()
            quote = [s[2:]]
            while i + 1 < len(lines) and lines[i + 1].startswith(">"):
                i += 1
                quote.append(lines[i][1:].strip())
            box(" ".join(quote))
        elif s.startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                if not re.match(r"^\|[\s:|-]+\|$", lines[i].strip()):
                    rows.append(split_row(lines[i]))
                i += 1
            i -= 1
            table(rows, widths, header)
            widths, header = None, True
        elif re.match(r"^(- |\d+\. )", s):
            flush()
            while i < len(lines) and re.match(r"^(- |\d+\. )", lines[i].strip()):
                item = lines[i].strip()
                bullet = "•" if item.startswith("- ") else item.split(".", 1)[0] + "."
                story.append(Paragraph(inline(item.split(" ", 1)[1]), BUL, bulletText=bullet))
                i += 1
            i -= 1
            story.append(Spacer(1, 4))
        elif (m := re.match(r'^!\[(.*)\]\(([^ )]+)(?: "([^"]*)")?\)$', s)):
            flush()
            opts = dict(kv.split("=", 1) for kv in (m.group(3) or "").split())
            picture(m.group(2), m.group(1), opts)
        else:
            para.append(s)
        i += 1
    flush()


parse(open(SRC, encoding="utf-8").read())
doc = Doc(OUT, pagesize=letter, leftMargin=0.85 * inch, rightMargin=0.85 * inch,
          topMargin=0.8 * inch, bottomMargin=0.95 * inch, title="%s user guide" % meta.get("title", ""),
          author="Stagg lab", subject=meta.get("subtitle", ""))
doc.multiBuild(story, onFirstPage=page_frame, onLaterPages=page_frame)
print("written", OUT)
