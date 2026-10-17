"""Stage 2 — crop every question and its mark scheme out of the PDFs as images.

For each paper in papers.json:
  * question paper: find "[Maximum mark: N]" starts, take each question from its start to
    the next, across pages; drop page furniture and the ruled answer boxes; stitch slices.
  * mark scheme: anchor sections on the longest 1, 2, 3 … chain of left-margin numbers
    (x < 84), assert it has one section per question, crop the same way.
Crops are rendered at 200 dpi greyscale (PNG cache in out/png) and normalised to lossless
WebP with an 8-level grey LUT (out/img). Results go to out/extract.json.

    .venv/bin/python -I extract.py [--force] [paper_id ...]
"""
import json
import os
import re
import sys
from pathlib import Path

import pymupdf
from PIL import Image

HERE = Path(__file__).resolve().parent
# folder of past-paper PDFs: IB_PAPERS_DIR, else the default below
SRC = Path(os.environ.get("IB_PAPERS_DIR", "~/Downloads/School/Math/Past Papers")).expanduser()
OUT = HERE / "out"
PNG, IMG = OUT / "png", OUT / "img"
DPI = 200
SCALE = DPI / 72

# Text column. Margin hatching sits outside it and alternates sides by page parity.
QP_X0, QP_X1, QP_WHITE = 36.0, 558.0, 553.6     # QP: blank everything right of QP_WHITE
MS_X0, MS_X1 = 36.0, 574.0
Y_TOP, Y_BOT = 62.0, 786.0                      # below the running header, above the footer
MS_Y_BOT = 812.0                                 # schemes have no "Turn over" footer; totals sit lower
GAP_MERGE = 40.0                                 # content closer than this stays joined
PAD = 4.0
MAX_CHUNK_PT = 720.0                             # split stitched crops so each fits a PDF page

FURNITURE = re.compile(
    r"^\s*(?:"
    r"[–-]\s*\d+\s*[–-]"                                   # "– 7 –" page number (+ barcode)
    r"|\d\dEP\d\d"                                          # footer code
    r"|\d{4}\s*[–-]\s*\d{4}M?\s*$"                          # bare barcode
    r"|[MN]\d\d/5/\S+"                                      # paper code
    r"|Turn over"
    r"|Do not write solutions on this page"
    r"|Please do not write on this page"
    r"|Answers written on this page"
    r"|\(Question \d+ continued\)"
    r"|\(This question continues on the following page\)"
    r"|Section [AB]\s*$"
    r"|Answer all questions"
    r"|Please start each question on a new page"
    r"|Full marks are not necessarily awarded"
    r"|Candidate session number"
    r"|©|International Baccalaureate|Organisation du Baccalauréat|Organización del Bachillerato"
    r"|References:|Acknowledg"
    r"|Zone [ABC]"
    r")", re.I)

RULE_CHARS = re.compile(r"[A-Za-z0-9]")


def is_rule(b):
    x0, y0, x1, y1, t = b[:5]
    return (x1 - x0) > 300 and (y1 - y0) < 24 and not RULE_CHARS.search(t)


_ITEMS = {}


def page_items(page, x0c, x1c, ybot=Y_BOT):
    """Content intervals and rule intervals (y ranges) on a page (cached: get_drawings is slow)."""
    key = (page.parent.name, page.number, x0c, x1c, ybot)
    if key not in _ITEMS:
        _ITEMS[key] = _page_items(page, x0c, x1c, ybot)
    return _ITEMS[key]


def _page_items(page, x0c, x1c, ybot):
    frames = []
    content, rules = [], []
    for b in page.get_text("blocks"):
        x0, y0, x1, y1, t = b[:5]
        if y1 < Y_TOP or y0 > ybot or not re.search(r"[^\s\x00-\x1f]", t):
            continue                                  # empty, or only invisible control glyphs (\x08 …)
        if is_rule(b):
            rules.append((y0, y1))
        elif not FURNITURE.search(t):
            content.append((y0, y1))
    drawings = page.get_drawings()
    # the page-footer barcode is a row of thin filled bars near the bottom of the page
    bars = [d["rect"] for d in drawings if d.get("fill") is not None and d["rect"].width < 4
            and d["rect"].y0 > 700 and d["rect"].height < 40]
    bar_band = (min(r.y0 for r in bars) - 2, max(r.y1 for r in bars) + 2) if len(bars) >= 10 else None
    for d in drawings:
        r = d["rect"]
        if r.y1 < Y_TOP or r.y0 > ybot:
            continue
        if bar_band and r.y0 >= bar_band[0] and r.y1 <= bar_band[1]:
            continue
        if r.height < 1.5 and r.width > 450:            # answer-box / frame horizontal border
            frames.append((r.y0 + r.y1) / 2)
            continue
        if r.x0 < x0c + 7 or r.x1 > x1c - 4:            # margin hatching, page frame
            continue
        if r.width >= 500 or (r.width < 1.5 and r.height > 400):
            continue
        # answer-box borders: vertical hairlines on either column edge, horizontal hairlines
        # spanning the column. A box only survives if something *inside* it is content.
        if r.width < 1.5 and (abs(r.x0 - 43) < 2.5 or abs(r.x0 - 553) < 2.5):
            continue
        content.append((r.y0, r.y1))
    for im in page.get_image_info():
        x0, y0, x1, y1 = im["bbox"]
        if y1 > Y_TOP and y0 < ybot:
            content.append((y0, y1))
    return content, rules, frames


def keep_intervals(content, rules, a, b, frames=()):
    """Merge content inside [a, b] into kept bands; never bridge across a rule band."""
    iv = sorted((max(a, y0), min(b, y1)) for y0, y1 in content if y1 > a and y0 < b)
    out = []
    for y0, y1 in iv:
        if out:
            p0, p1 = out[-1]
            gap_has_rule = any(r0 >= p1 - 1 and r1 <= y0 + 1 for r0, r1 in rules)
            if y0 - p1 < GAP_MERGE and not gap_has_rule:
                out[-1] = (p0, max(p1, y1))
                continue
            if y0 <= p1:
                out[-1] = (p0, max(p1, y1))
                continue
        out.append((y0, y1))
    padded = []
    for y0, y1 in out:
        top, bot = max(a, y0 - PAD), min(b, y1 + PAD)
        # never let the padding reach an answer-box border just above or below the content
        for f in frames:
            if y1 - 3 <= f <= bot + 2:                  # text bboxes can overhang a border by a point or two
                bot = min(bot, f - 0.6)
            if top - 2 <= f <= y0 + 3:
                top = max(top, f + 0.6)
        padded.append((top, bot))
    return padded


def render(page, x0, x1, y0, y1, white_from=None):
    pix = page.get_pixmap(dpi=DPI, clip=pymupdf.Rect(x0, y0, x1, y1), colorspace=pymupdf.csGRAY)
    img = Image.frombytes("L", (pix.width, pix.height), pix.samples)
    if white_from is not None:
        cut = int(round((white_from - x0) * SCALE))
        img.paste(255, (cut, 0, img.width, img.height))
    return img


def stitch(slices, gap_px=int(10 * SCALE)):
    """Stack slices; start a new chunk when the next slice would overflow MAX_CHUNK_PT."""
    if not slices:
        return []
    limit = MAX_CHUNK_PT * SCALE
    chunks, cur, h = [], [], 0
    for im in slices:
        if cur and h + gap_px + im.height > limit:
            chunks.append(cur)
            cur, h = [], 0
        h += (gap_px if cur else 0) + im.height
        cur.append(im)
    chunks.append(cur)
    out = []
    for c in chunks:
        w = max(i.width for i in c)
        H = sum(i.height for i in c) + gap_px * (len(c) - 1)
        canvas = Image.new("L", (w, H), 255)
        y = 0
        for i in c:
            canvas.paste(i, (0, y))
            y += i.height + gap_px
        out.append(canvas)
    return out


LUT = [round(round(v / 255 * 7) / 7 * 255) for v in range(256)]


def clear(stem):
    """Remove every earlier crop for this stem (both formats), so a re-run never leaves strays."""
    for old in [*IMG.glob(f"{stem}_*.webp"), *PNG.glob(f"{stem}_*.png")]:
        old.unlink()


def save(images, stem):
    names = []
    for k, im in enumerate(images):
        name = f"{stem}_{k}"
        im.save(PNG / f"{name}.png", optimize=True)
        im.point(LUT).save(IMG / f"{name}.webp", lossless=True, quality=100, method=4)
        names.append(f"{name}.webp")
    return names


def line_top(page, y, y1=None):
    """Top of every text line spanning the vertical midpoint of the line at y..y1 (tall
    fractions start above the margin number). Works on lines, not blocks — a legacy block can
    hold the previous "[6 marks]" and the next "2." — and needs the midpoint, so a "Total"
    line that merely touches the number's top edge stays with the previous question."""
    mid = (y + (y1 if y1 is not None else y + 12)) / 2
    tops = []
    for blk in page.get_text("dict")["blocks"]:
        for line in blk.get("lines", []):
            ly0, ly1 = line["bbox"][1], line["bbox"][3]
            if ly0 < mid < ly1 and ly0 > y - 40:
                tops.append(ly0)
    return min([y] + tops)


def crop_range(doc, start, end, x0c, x1c, white=None, stop_unless=None, ybot=Y_BOT):
    """Crop from (page, y) start to (page, y) end. stop_unless: regex a continuation page must match."""
    (ps, ys), (pe, ye) = start, end
    slices = []
    for pn in range(ps, pe + 1):
        page = doc[pn]
        if pn > ps and stop_unless and not re.search(stop_unless, page.get_text()):
            break
        a = ys if pn == ps else Y_TOP
        b = ye if pn == pe else ybot
        content, rules, frames = page_items(page, x0c, x1c, ybot)
        for y0, y1 in keep_intervals(content, rules, a, b, frames):
            if y1 - y0 > 10 + 2 * PAD:          # slivers are stray hairlines, not content
                slices.append(render(page, x0c, x1c, y0, y1, white))
    return slices


# ---------- question papers --------------------------------------------------------------
START = re.compile(r"^\s*(\d{1,2})\.\s*\[\s*Maximum mark:\s*(\d+)\s*\]")


def qp_starts(doc):
    starts = []
    for pn, page in enumerate(doc):
        for b in page.get_text("blocks"):
            m = START.search(b[4])
            if m:
                starts.append({"q": int(m.group(1)), "marks": int(m.group(2)), "page": pn, "y": b[1]})
    return starts


# ---------- mark schemes -----------------------------------------------------------------
def page_spans(page):
    out = []
    for blk in page.get_text("dict")["blocks"]:
        for line in blk.get("lines", []):
            for sp in line["spans"]:
                if sp["text"].strip():
                    out.append((sp["bbox"], sp["text"].strip(), sp["size"]))
    return out


def ms_starts(doc, n_expected):
    cands = []
    for pn, page in enumerate(doc):
        if pn < 2:
            continue
        spans = page_spans(page)
        for (x0, y0, x1, y1), t, size in spans:
            m = re.fullmatch(r"(\d{1,2})\.?", t)
            if not (m and x0 < 84 and Y_TOP <= y0 <= Y_BOT and size >= 8):
                continue
            # a margin number has nothing to its left on its line (rejects subscripts like u₁)
            mid = (y0 + y1) / 2
            if any(bx1 <= x0 + 0.5 and by0 < mid < by1 for (bx0, by0, bx1, by1), _, _ in spans):
                continue
            cands.append((pn, y0, int(m.group(1)), y1))
    cands.sort()
    # longest chains 1, 2, 3 … in document order (DP over predecessors with value v-1)
    best, prev = [0] * len(cands), [-1] * len(cands)
    for i, (_, _, v, _) in enumerate(cands):
        if v == 1:
            best[i] = 1
        for j in range(i):
            # ">=": on ties link to the *latest* predecessor, so a real section 2 chains to
            # the real section 1 rather than to the decoy "1" on an instruction page
            if cands[j][2] == v - 1 and best[j] and best[j] + 1 >= best[i]:
                best[i], prev[i] = best[j] + 1, j
    ends = [i for i in range(len(cands)) if best[i]]
    if not ends:
        return []
    # the questions come after the instruction-page decoys: among chains of the expected
    # length prefer the one that starts last; otherwise take the longest
    def chain(i):
        c = []
        while i != -1:
            c.append(i)
            i = prev[i]
        return c[::-1]
    full = [chain(i) for i in ends if best[i] == n_expected]
    pick = max(full, key=lambda c: (cands[c[0]][0], cands[c[0]][1])) if full else chain(max(ends, key=lambda i: best[i]))
    return [{"q": cands[i][2], "page": cands[i][0], "y": cands[i][1], "y1": cands[i][3]} for i in pick]


def range_text(doc, start, end):
    (ps, ys), (pe, ye) = start, end
    parts = []
    for pn in range(ps, pe + 1):
        a = ys if pn == ps else Y_TOP
        b = ye if pn == pe else MS_Y_BOT
        parts.append(doc[pn].get_text(clip=pymupdf.Rect(0, a, 600, b)))
    return " ".join(parts)


def ms_total(text):
    """The question total a scheme section states: its last "Total [N marks]", else its last "[N marks]"
    (single-part questions often give several METHODs, each ending in the same "[N marks]")."""
    tot = re.findall(r"Total\s*\[\s*(\d+)\s*marks?\s*\]", text, re.I)
    if tot:
        return int(tot[-1])
    parts = [int(x) for x in re.findall(r"\[\s*(\d+)\s*marks?\s*\]", text, re.I)]
    return parts[-1] if parts else None


def last_content_page(doc):
    for pn in range(doc.page_count - 1, -1, -1):
        c, _, _ = page_items(doc[pn], MS_X0, MS_X1, MS_Y_BOT)
        if c:
            return pn
    return doc.page_count - 1


def process(paper, force=False):
    pid = paper["id"]
    res = {"id": pid, "questions": [], "problems": []}
    qp = pymupdf.open(SRC / paper["qp_file"])
    starts = qp_starts(qp)
    nums = [s["q"] for s in starts]
    if nums != list(range(1, len(nums) + 1)):
        res["problems"].append(f"QP question numbers not 1..n: {nums}")
    if [s["marks"] for s in starts] != paper["marks"]:
        res["problems"].append(f"QP marks {[s['marks'] for s in starts]} != papers.json {paper['marks']}")

    for i, s in enumerate(starts):
        if i + 1 < len(starts):
            nx = starts[i + 1]
            end, stop = (nx["page"], line_top(qp[nx["page"]], nx["y"]) - 2), None
        else:
            end, stop = (qp.page_count - 1, Y_BOT), rf"\(Question {s['q']} continued\)"
        stem = f"{pid}_q{s['q']:02d}"
        if not force and (IMG / f"{stem}_0.webp").exists():
            qi = sorted(p.name for p in IMG.glob(f"{stem}_*.webp"))
        else:
            clear(stem)
            top = line_top(qp[s["page"]], s["y"]) - 3
            sl = crop_range(qp, (s["page"], top), end, QP_X0, QP_X1, QP_WHITE, stop)
            qi = save(stitch(sl), stem)
        text = []
        last_page = end[0] if stop is None else s["page"]
        for pn in range(s["page"], end[0] + 1):
            t = qp[pn].get_text()
            if pn > s["page"] and stop and not re.search(stop, t):
                break
            text.append(t)
        res["questions"].append({"q": s["q"], "marks": s["marks"], "qp_page": s["page"] + 1, "qi": qi,
                                 "text": re.sub(r"\s+", " ", " ".join(text))[:4000], "mi": []})

    if paper["ms_file"]:
        ms = pymupdf.open(SRC / paper["ms_file"])
        ms_s = ms_starts(ms, len(starts))
        res["ms_sections"] = len(ms_s)
        if len(ms_s) != len(starts):
            res["problems"].append(f"MS sections found {len(ms_s)} != questions {len(starts)}: "
                                   f"{[(x['q'], x['page'] + 1) for x in ms_s]}")
        else:
            last = last_content_page(ms)
            for i, s in enumerate(ms_s):
                if i + 1 < len(ms_s):
                    nx = ms_s[i + 1]
                    end = (nx["page"], line_top(ms[nx["page"]], nx["y"], nx["y1"]) - 2)
                else:
                    end = (last, MS_Y_BOT)
                top = line_top(ms[s["page"]], s["y"], s["y1"]) - 3
                stem = f"{pid}_ms{s['q']:02d}"
                if not force and (IMG / f"{stem}_0.webp").exists():
                    mi = sorted(p.name for p in IMG.glob(f"{stem}_*.webp"))
                else:
                    clear(stem)
                    mi = save(stitch(crop_range(ms, (s["page"], top), end, MS_X0, MS_X1, ybot=MS_Y_BOT)), stem)
                res["questions"][i]["mi"] = mi
                stated = ms_total(range_text(ms, (s["page"], top), end))
                res["questions"][i]["ms_stated_total"] = stated
                if stated != res["questions"][i]["marks"]:
                    res["problems"].append(f"MS section {s['q']} (p{s['page'] + 1}) states {stated} marks, "
                                           f"question has {res['questions'][i]['marks']}")
                res["questions"][i]["ms_page"] = s["page"] + 1
    return res


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    PNG.mkdir(parents=True, exist_ok=True)
    IMG.mkdir(parents=True, exist_ok=True)
    papers = json.loads((HERE / "papers.json").read_text())
    cache = OUT / "extract.json"
    db = json.loads(cache.read_text()) if cache.exists() else {}
    for p in papers:
        if args and p["id"] not in args:
            continue
        try:
            r = process(p, force)
        except Exception as e:                         # report, don't skip silently
            r = {"id": p["id"], "questions": [], "problems": [f"FAILED: {e!r}"]}
        db[p["id"]] = r
        nq = len(r["questions"])
        nqi = sum(len(q["qi"]) for q in r["questions"])
        nmi = sum(len(q["mi"]) for q in r["questions"])
        flag = "  !! " + " | ".join(r["problems"]) if r["problems"] else ""
        print(f"{p['id']:10} Qs {nq:2}/{p['questions']:2}  q-imgs {nqi:3}  ms-sections {r.get('ms_sections', '-')!s:>2}  ms-imgs {nmi:3}{flag}")
    cache.write_text(json.dumps(db, indent=1, ensure_ascii=False))
    probs = {k: v["problems"] for k, v in db.items() if v["problems"]}
    print(f"\n{len(db)} papers, {sum(len(v['questions']) for v in db.values())} questions; "
          f"{len(probs)} with problems")


if __name__ == "__main__":
    main()
