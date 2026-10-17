"""Stage 6 — one PDF per syllabus topic, built with ReportLab's BaseDocTemplate.

Each PDF: cover page, a clickable contents key (sub-topic headings and question entries that
jump to the question), then every question under its sub-topic heading: a header line, the
question image(s), and the mark scheme straight after. Authored mark schemes get amber
styling and the header "MARK SCHEME — UNOFFICIAL, WORKED FOR THIS COMPILATION". Sidebar
bookmarks come from a custom Anchor flowable (bookmarkPage + addOutlineEntry).

    .venv/bin/python -I build_pdfs.py            build dist/IB Maths AA HL - Topic N - <Name>.pdf
    .venv/bin/python -I build_pdfs.py --verify   only re-check the PDFs already in dist/
"""
import json
import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path
from xml.sax.saxutils import escape

import pymupdf
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Flowable, Frame, Image, KeepTogether,
                                NextPageTemplate, PageBreak, PageTemplate, Paragraph, Spacer, Table,
                                TableStyle)

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from syllabus import SYLLABUS, TOPICS  # noqa: E402

OUT, DIST = HERE / "out", HERE / "dist"
TMP = OUT / "pdf_png"
PAGE_W, PAGE_H = A4
MARGIN = 16 * mm
FRAME_W = PAGE_W - 2 * MARGIN
FRAME_H = PAGE_H - 2 * MARGIN - 8 * mm          # room for the footer

TOPIC_COLOUR = {1: "#2f5fb3", 2: "#6b46c1", 3: "#1d7f5f", 4: "#b83262", 5: "#1b7a94"}
AMBER, AMBER_FILL, AMBER_INK = "#c48012", "#ffecb3", "#6e3e00"
GREY_INK, RULE = "#5b6270", "#d5d9e0"

# ---- fonts: base faces plus a glyph fallback chain ------------------------------------------
SUP = "/System/Library/Fonts/Supplemental/"
pdfmetrics.registerFont(TTFont("Arial", SUP + "Arial.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Bold", SUP + "Arial Bold.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Italic", SUP + "Arial Italic.ttf"))
pdfmetrics.registerFont(TTFont("ArialUni", SUP + "Arial Unicode.ttf"))
pdfmetrics.registerFont(TTFont("Geneva", "/System/Library/Fonts/Geneva.ttf"))
pdfmetrics.registerFontFamily("Arial", normal="Arial", bold="Arial-Bold", italic="Arial-Italic",
                              boldItalic="Arial-Bold")
FALLBACK = ["ArialUni", "Geneva"]
_CMAP = {}

# modifier letters no installed TrueType font has: draw as <sub>/<super> of the plain letter
SUBS = dict(zip("ₐₑₒₓₕₖₗₘₙₚₛₜ₀₁₂₃₄₅₆₇₈₉₊₋", "aeoxhklmnpst0123456789+−"))
SUPS = dict(zip("ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖʳˢᵗᵘᵛʷˣʸᶻ⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻", "abcdefghijklmnoprstuvwxyz0123456789+−"))


def has(font, ch):
    if font not in _CMAP:
        _CMAP[font] = pdfmetrics.getFont(font).face.charToGlyph
    return ord(ch) in _CMAP[font]


def rich(text, base="Arial"):
    """Escape text for a Paragraph, switching font per character where `base` lacks a glyph."""
    out = []
    for ch in text:
        if ch.isspace() or has(base, ch):
            out.append(escape(ch))
            continue
        f = next((f for f in FALLBACK if has(f, ch)), None)
        if f:
            out.append(f'<font name="{f}">{escape(ch)}</font>')
        elif ch in SUBS:
            out.append(f'<sub rise="1.6" size="6.5">{escape(SUBS[ch])}</sub>')   # gentle subscript
        elif ch in SUPS:
            out.append(f'<super rise="3.2" size="6.5">{escape(SUPS[ch])}</super>')    # gentle superscript
        else:
            raise ValueError(f"no glyph for {ch!r} (U+{ord(ch):04X}) in {text!r}")
    return "".join(out).replace("</font><font name=\"ArialUni\">", "")


def S(name, **kw):
    base = dict(fontName="Arial", fontSize=9.5, leading=12.5, textColor=colors.HexColor("#1f2329"))
    base.update(kw)
    return ParagraphStyle(name, **base)


ST = {
    "cover_kicker": S("ck", fontSize=11, textColor=colors.HexColor(GREY_INK), leading=14),
    "cover_title": S("ct", fontName="Arial-Bold", fontSize=30, leading=36),
    "cover_sub": S("cs", fontSize=13, leading=18, textColor=colors.HexColor(GREY_INK)),
    "body": S("b", fontSize=10, leading=14),
    "small": S("s", fontSize=8.5, leading=11, textColor=colors.HexColor(GREY_INK)),
    "toc_h": S("th", fontName="Arial-Bold", fontSize=10.5, leading=14, spaceBefore=7, spaceAfter=2),
    "toc_e": S("te", fontSize=8.8, leading=11.6, leftIndent=12),
    "sub_h": S("sh", fontName="Arial-Bold", fontSize=14, leading=18, textColor=colors.white),
    "q_h": S("qh", fontName="Arial-Bold", fontSize=10.5, leading=13.5),
    "q_d": S("qd", fontSize=9, leading=12, textColor=colors.HexColor(GREY_INK)),
    "ms_h": S("mh", fontName="Arial-Bold", fontSize=9, leading=11, textColor=colors.HexColor(GREY_INK)),
    "ms_h_au": S("ma", fontName="Arial-Bold", fontSize=9, leading=11, textColor=colors.HexColor(AMBER_INK)),
    "back": S("bk", fontSize=8, leading=10, textColor=colors.HexColor(GREY_INK), alignment=2),
}


class Anchor(Flowable):
    """Zero-size flowable: a named destination plus a sidebar outline entry."""

    def __init__(self, key, title=None, level=0):
        super().__init__()
        self.key, self.title, self.level = key, title, level
        self.width = self.height = 0

    def wrap(self, aw, ah):
        return 0, 0

    def draw(self):
        self.canv.bookmarkPage(self.key)
        if self.title:
            self.canv.addOutlineEntry(self.title, self.key, level=self.level, closed=self.level == 0)


class Rule(Flowable):
    def __init__(self, colour=RULE, width=0.6, space=4):
        super().__init__()
        self.colour, self.lw, self.space = colour, width, space

    def wrap(self, aw, ah):
        self.width = aw
        return aw, self.space * 2

    def draw(self):
        self.canv.setStrokeColor(colors.HexColor(self.colour))
        self.canv.setLineWidth(self.lw)
        self.canv.line(0, self.space, self.width, self.space)


def band(text_html, style, fill, pad=5, border=None):
    """A full-width coloured band holding one paragraph."""
    t = Table([[Paragraph(text_html, style)]], colWidths=[FRAME_W])
    cmds = [("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(fill)),
            ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), pad), ("BOTTOMPADDING", (0, 0), (-1, -1), pad)]
    if border:
        cmds.append(("BOX", (0, 0), (-1, -1), 1, colors.HexColor(border)))
    t.setStyle(TableStyle(cmds))
    return t


# ---- images ---------------------------------------------------------------------------------
def png_for(webp):
    """ReportLab's Image needs a file path: write a temp PNG (palette for 8-level greys)."""
    TMP.mkdir(parents=True, exist_ok=True)
    dst = TMP / webp.replace(".webp", ".png")
    src = OUT / "img" / webp
    if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
        im = PILImage.open(src)
        if im.mode == "L":
            im = im.convert("P", palette=PILImage.ADAPTIVE, colors=8)
        im.save(dst, optimize=True)
    return dst


def image_flowable(webp, max_h):
    path = png_for(webp)
    w, h = PILImage.open(path).size
    scale = FRAME_W / w
    if h * scale > max_h:                         # never taller than the frame
        scale = max_h / h
    img = Image(str(path), width=w * scale, height=h * scale)
    img.hAlign = "LEFT"
    return img


# ---- document -------------------------------------------------------------------------------
def anchor_id(qid):
    return "q_" + re.sub(r"[^A-Za-z0-9]", "_", qid)


def sub_anchor(code):
    return "sub_" + re.sub(r"[^A-Za-z0-9]", "_", code)


def footer(topic):
    def draw(canv, doc):
        canv.saveState()
        canv.setFont("Arial", 7.5)
        canv.setFillColor(colors.HexColor(GREY_INK))
        canv.drawString(MARGIN, MARGIN - 4 * mm,
                        f"IB Maths AA HL · Topic {topic} · {TOPICS[topic]}  —  past-paper compilation for personal study")
        canv.drawRightString(PAGE_W - MARGIN, MARGIN - 4 * mm, f"{doc.page}")
        canv.restoreState()
    return draw


def build_topic(topic, records):
    colour = TOPIC_COLOUR[topic]
    fname = DIST / f"IB Maths AA HL - Topic {topic} - {TOPICS[topic]}.pdf"
    doc = BaseDocTemplate(str(fname), pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN,
                          topMargin=MARGIN, bottomMargin=MARGIN + 6 * mm,
                          title=f"IB Maths AA HL — Topic {topic}: {TOPICS[topic]}",
                          author="Compiled from IB past papers for personal study",
                          subject="Questions with mark schemes, grouped by syllabus sub-topic")
    frame = Frame(MARGIN, MARGIN + 6 * mm, FRAME_W, FRAME_H, id="f", leftPadding=0, rightPadding=0,
                  topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate("cover", [frame]), PageTemplate("body", [frame], onPage=footer(topic))])

    groups = OrderedDict()
    for r in records:
        groups.setdefault(r["code"], []).append(r)

    story = []
    # cover
    n_q, n_m = len(records), sum(r["marks"] for r in records)
    n_auth = sum(r["msAuthored"] for r in records)
    sessions = sorted({(r["year"], r["session"]) for r in records}, reverse=True)
    story += [Anchor("cover", "Cover", 0), Spacer(1, 50 * mm),
              Paragraph("IB MATHEMATICS: ANALYSIS AND APPROACHES · HIGHER LEVEL", ST["cover_kicker"]),
              Spacer(1, 4 * mm), Rule(colour, 3, 2), Spacer(1, 6 * mm),
              Paragraph(f"Topic {topic}", S("ctn", fontName="Arial-Bold", fontSize=16, leading=20,
                                             textColor=colors.HexColor(colour))),
              Paragraph(rich(TOPICS[topic], "Arial-Bold"), ST["cover_title"]), Spacer(1, 6 * mm),
              Paragraph(f"{n_q} questions · {n_m} marks · {len(groups)} sub-topics", ST["cover_sub"]),
              Paragraph(f"Past papers {sessions[-1][1]} {sessions[-1][0]} – {sessions[0][1]} {sessions[0][0]}, "
                        f"Papers 1 and 2", ST["cover_sub"]),
              Spacer(1, 14 * mm),
              Paragraph("Each question is followed immediately by its mark scheme. Questions are grouped "
                        "by syllabus sub-topic, newest first. Click any entry in the contents to jump to it; "
                        "every question has a link back to the contents, and the PDF sidebar bookmarks "
                        "follow the same structure.", ST["body"])]
    if n_auth:
        story += [Spacer(1, 5 * mm),
                  band(f"<b>{n_auth} question{'s' if n_auth > 1 else ''} in this topic use an UNOFFICIAL mark "
                       "scheme</b>, worked for this compilation because the IB scheme was not available "
                       "(May 2017 Paper 1 TZ2). These are shaded amber wherever they appear and are not IB documents.",
                       S("cw", fontSize=9.5, leading=13, textColor=colors.HexColor(AMBER_INK)), AMBER_FILL,
                       pad=7, border=AMBER)]
    story += [Spacer(1, 30 * mm),
              Paragraph("Question papers and mark schemes © International Baccalaureate Organization. "
                        "Compiled for the owner's personal revision only — not for distribution.", ST["small"]),
              NextPageTemplate("body"), PageBreak()]

    # contents key
    story += [Anchor("toc", "Contents", 0),
              Paragraph(f"Contents — Topic {topic}: {rich(TOPICS[topic], 'Arial-Bold')}",
                        S("tt", fontName="Arial-Bold", fontSize=16, leading=20, spaceAfter=6)),
              Rule(colour, 1.5, 3)]
    for code, rs in groups.items():
        head = (f'<a href="#{sub_anchor(code)}" color="{colour}">{escape(code)}</a>&nbsp;&nbsp;'
                f'<a href="#{sub_anchor(code)}">{rich(SYLLABUS[code], "Arial-Bold")}</a>'
                f'<font name="Arial" size="8.5" color="{GREY_INK}">&nbsp;&nbsp;{len(rs)} question'
                f'{"s" if len(rs) > 1 else ""} · {sum(r["marks"] for r in rs)} marks</font>')
        entries = [Paragraph(head, ST["toc_h"])]
        for r in rs:
            au = (f'&nbsp;<font color="{AMBER}" name="Arial-Bold">[unofficial MS]</font>'
                  if r["msAuthored"] else "")
            entries.append(Paragraph(
                f'<a href="#{anchor_id(r["id"])}"><font color="{GREY_INK}">{escape(r["label"])} · Q{r["q"]} · '
                f'{r["marks"]} marks</font> — {rich(r["desc"])}</a>{au}', ST["toc_e"]))
        story.append(KeepTogether(entries[:3]))
        story += entries[3:]
    story.append(PageBreak())

    # questions
    for code, rs in groups.items():
        story += [CondPageBreak(90 * mm), Anchor(sub_anchor(code), f"{code}  {SYLLABUS[code]}", 0),
                  band(f'{escape(code)}&nbsp;&nbsp;{rich(SYLLABUS[code], "Arial-Bold")}', ST["sub_h"], colour, pad=6),
                  Spacer(1, 4 * mm)]
        for r in rs:
            title = f"{r['label']} · Q{r['q']} ({r['marks']})  [{r['id']}]"
            head = Table([[Paragraph(f'{escape(r["label"])} — Question {r["q"]}'
                                     f'<font color="{GREY_INK}" name="Arial"> · {r["marks"]} marks · '
                                     f'{"calculator" if r["calc"] else "no calculator"} · '
                                     f'Section {r["section"]}</font>', ST["q_h"]),
                           Paragraph(f'<a href="#toc">↑ back to contents</a>', ST["back"])]],
                         colWidths=[FRAME_W * 0.78, FRAME_W * 0.22])
            head.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                      ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                                      ("VALIGN", (0, 0), (-1, -1), "BOTTOM")]))
            desc = Paragraph(f'{rich(r["desc"])} <font color="#9aa1ad" size="7.5">· {escape(r["id"])}</font>', ST["q_d"])
            hdr_h = 30
            q_imgs = [image_flowable(f, FRAME_H - hdr_h - 10) for f in r["qi"]]
            story.append(KeepTogether([Anchor(anchor_id(r["id"]), title, 1), head, desc, Rule(colour, 1, 3),
                                       q_imgs[0]]))
            story += q_imgs[1:]
            if r["msAuthored"]:
                ms_head = band("MARK SCHEME — UNOFFICIAL, WORKED FOR THIS COMPILATION &nbsp;"
                               '<font name="Arial" size="8">(not an IB document; results verified with sympy)</font>',
                               ST["ms_h_au"], AMBER_FILL, pad=4, border=AMBER)
            else:
                ms_head = band("MARK SCHEME", ST["ms_h"], "#eef0f3", pad=3)
            m_imgs = [image_flowable(f, FRAME_H - 30) for f in r["mi"]]
            story += [Spacer(1, 3 * mm), KeepTogether([ms_head, Spacer(1, 2 * mm), m_imgs[0]])] + m_imgs[1:]
            story += [Spacer(1, 4 * mm), Rule(RULE, 0.8, 4), Spacer(1, 3 * mm)]

    doc.build(story)
    return fname


# ---- verification -----------------------------------------------------------------------------
def verify(db):
    """Read the PDFs back: every question exactly once, every link and bookmark resolves."""
    files = sorted(DIST.glob("IB Maths AA HL - Topic *.pdf"))
    assert len(files) == 5, f"expected 5 PDFs, found {len(files)}"
    seen = Counter()
    ok = True
    for f in files:
        doc = pymupdf.open(f)
        n = doc.page_count
        toc = doc.get_toc(simple=False)
        ids = [re.search(r"\[([^\]]+)\]$", e[1]).group(1) for e in toc if e[0] == 2]
        seen.update(ids)
        # bookmarks: each question bookmark lands on a page whose text carries that question id
        bad_bm = []
        for lvl, title, page, *_ in toc:
            if not (1 <= page <= n):                                   # get_toc pages are 1-based
                bad_bm.append(title)
            elif lvl == 2:
                qid = re.search(r"\[([^\]]+)\]$", title).group(1)
                if qid not in doc[page - 1].get_text():                # load_page / doc[i] are 0-based
                    bad_bm.append(title)
        # links: LINK_GOTO / LINK_NAMED targets are 0-based page numbers — compare with 0..n-1
        n_links, bad_links = 0, []
        for p in doc:
            for ln in p.get_links():
                if ln["kind"] in (pymupdf.LINK_GOTO, pymupdf.LINK_NAMED):
                    n_links += 1
                    tgt = ln.get("page", -1)
                    if not (0 <= tgt < n):
                        bad_links.append((p.number + 1, ln.get("nameddest") or ln.get("name"), tgt))
        topic = int(re.search(r"Topic (\d)", f.name).group(1))
        expect = sum(1 for r in db if r["topic"] == topic)
        status = "OK" if not bad_links and not bad_bm and len(ids) == expect else "!!"
        ok &= status == "OK"
        print(f"  {status} {f.name}: {n} pages, {len(ids)}/{expect} questions, {n_links} internal links "
              f"({len(bad_links)} broken), {len(toc)} bookmarks ({len(bad_bm)} bad), {f.stat().st_size / 1e6:.1f} MB")
        for b in bad_links[:5] + bad_bm[:5]:
            print("     ", b)
    all_ids = {r["id"] for r in db}
    dup = [k for k, v in seen.items() if v > 1]
    missing = sorted(all_ids - set(seen))
    extra = sorted(set(seen) - all_ids)
    print(f"  questions across PDFs: {sum(seen.values())} placements, {len(seen)} distinct, "
          f"{len(all_ids)} in db; duplicates {dup}, missing {missing}, unknown {extra}")
    ok &= not dup and not missing and not extra
    print("PDF verification:", "PASSED" if ok else "FAILED")
    return ok


def main():
    db = json.loads((OUT / "db.json").read_text())
    if "--verify" not in sys.argv:
        DIST.mkdir(exist_ok=True)
        for t in TOPICS:
            recs = [r for r in db if r["topic"] == t]
            f = build_topic(t, recs)
            print(f"built {f.name}: {len(recs)} questions")
    sys.exit(0 if verify(db) else 1)


if __name__ == "__main__":
    main()
