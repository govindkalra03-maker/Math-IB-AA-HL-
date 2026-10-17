"""Stage 5 — write and render mark schemes for questions that arrived without one.

Only May 2017 · Paper 1 · TZ2 needs this. The schemes below are laid out in IB style
(M1 method, A1 answer, R1 reasoning, AG answer given, brackets for implied marks). Before
anything is rendered:
  * every result is verified symbolically (verify_ms.py);
  * the marks in each part (first METHOD only, when alternatives are given) must equal the
    part mark printed on the question paper, and each question's parts must sum to its
    [Maximum mark] — asserted in code.
Images get an amber "UNOFFICIAL MARK SCHEME" banner and an amber edge stripe on every chunk,
and are kept in colour so they can never be mistaken for scanned IB schemes.

    .venv/bin/python -I author_ms.py
Writes out/img/<paper>_ams<q>_<k>.webp (+ PNG) and out/authored.json.
"""
import json
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import verify_ms  # noqa: E402

OUT = HERE / "out"
PAPER = "M17P1TZ2"
LABEL = "May 2017 · Paper 1 · TZ2"

# ---------------------------------------------------------------------------------------
# Scheme content.  A part is (label, stated_marks, lines). A line is (indent, text, marks)
# with $…$ marking maths; ("METHOD", "METHOD 2") starts an alternative; ("NOTE", text) is a
# boxed examiner note; ("SKETCH", name) inserts a drawn sketch.  C(n, r) is the binomial
# coefficient.
# ---------------------------------------------------------------------------------------
SCHEMES = {
    1: [(None, 5, [
        (0, "general term $C(10, r)(2x²)¹⁰⁻ʳ(2x³)⁻ʳ$", "(M1)"),
        (0, "$= C(10, r)·2¹⁰⁻²ʳ·x²⁰⁻⁵ʳ$", "(A1)"),
        (0, "term independent of x when $20 − 5r = 0$", "M1"),
        (0, "$r = 4$", "A1"),
        (0, "term $= C(10, 4)·2² = 210 × 4 = 840$", "A1"),
        ("NOTE", "If the expansion is set up with the powers the other way round, r = 6; award equivalent marks."),
    ])],
    2: [("(a)", 2, [
        (0, "$−11 ≤ f(x) ≤ 21$", "A1A1"),
        ("NOTE", "Award A1 for each end point with the correct inequality; accept [−11, 21]."),
    ]), ("(b)", 2, [
        (0, "$x = 2y³ + 5$  (interchanging x and y)", "M1"),
        (0, "$f⁻¹(x) = ∛((x − 5)/2)$", "A1"),
    ]), ("(c)", 2, [
        (0, "domain: $−11 ≤ x ≤ 21$", "A1FT"),
        (0, "range: $−2 ≤ f⁻¹(x) ≤ 2$", "A1"),
        ("NOTE", "Follow through the domain from their answer to part (a)."),
    ])],
    3: [("(a)", 4, [
        (0, "$u₄ = 9 + 3d$,  $u₈ = 9 + 7d$", "(A1)"),
        (0, "$(9 + 3d)/9 = (9 + 7d)/(9 + 3d)$  or  $(9 + 3d)² = 9(9 + 7d)$", "M1"),
        (0, "$81 + 54d + 9d² = 81 + 63d  ⇒  9d² − 9d = 0$", "A1"),
        (0, "$d = 1$  (since $d ≠ 0$)", "A1"),
    ]), ("(b)", 1, [
        (0, "$r = 12/9 = 4/3$", "A1"),
    ])],
    4: [("(a)", 5, [
        (0, "$v = ds/dt = 1 − 2 sin 2t$", "M1A1"),
        (0, "at rest: $1 − 2 sin 2t = 0  ⇒  sin 2t = 1/2$", "M1"),
        (0, "$2t = π/6, 5π/6, …$", ""),
        (0, "$t₁ = π/12$", "A1"),
        (0, "$t₂ = 5π/12$", "A1"),
    ]), ("(b)", 2, [
        (0, "$s = π/12 + cos(π/6)$", "(M1)"),
        (0, "$= π/12 + √3/2$  (metres)", "A1"),
    ])],
    5: [(None, 4, [
        (0, "$→BA$ corresponds to $(−1 + 4i) − (−3) = 2 + 4i$", "(A1)"),
        (0, "$→BC$ is $→BA$ rotated 90° clockwise: $(2 + 4i)(−i) = 4 − 2i$", "M1"),
        (0, "C: $−3 + (4 − 2i) = 1 − 2i$", "A1"),
        (0, "D: $(−1 + 4i) + (4 − 2i) = 3 + 2i$", "A1"),
        ("NOTE", "Accept equivalent methods, e.g. using gradients and lengths of the sides."),
    ])],
    6: [("(a)", 4, [
        (0, "$dx = sec²θ dθ$", "A1"),
        (0, "$∫ sec²θ/(tan²θ + 1)² dθ$", "M1"),
        (0, "$= ∫ sec²θ/sec⁴θ dθ = ∫ cos²θ dθ$", "A1"),
        (0, "$x = 0 ⇒ θ = 0$,  $x = 1 ⇒ θ = π/4$", "A1"),
        (0, "so $∫₀¹ 1/(x² + 1)² dx = ∫₀^{π/4} cos²θ dθ$", "AG"),
    ]), ("(b)", 3, [
        (0, "$∫₀^{π/4} cos²θ dθ = ∫₀^{π/4} ½(1 + cos 2θ) dθ$", "M1"),
        (0, "$= [θ/2 + (sin 2θ)/4]₀^{π/4}$", "A1"),
        (0, "$= π/8 + 1/4$", "A1"),
    ])],
    7: [("(a)", 3, [
        (0, "$P(X > 0) = 1 − P(X = 0) = 1 − e^{−m}$", "(M1)"),
        (0, "$1 − e^{−m} = 3/4  ⇒  e^{−m} = 1/4$", "A1"),
        (0, "$m = ln 4$", "A1"),
    ]), ("(b)", 4, [
        (0, "$Y ~ Po(2 ln 4) = Po(ln 16)$", "(A1)"),
        (0, "$P(Y > 1) = 1 − P(Y = 0) − P(Y = 1)$", "(M1)"),
        (0, "$= 1 − e^{−ln 16}(1 + ln 16) = 1 − (1 + ln 16)/16$", "A1"),
        (0, "$= (15 − ln 16)/16$", "A1"),
    ])],
    8: [(None, 9, [
        (0, "let P(n) be the statement; write C(n, r) for the binomial coefficient", ""),
        (0, "n = 3:  LHS $= C(2, 2) = 1$,  RHS $= C(3, 3) = 1$, so P(3) is true", "A1"),
        (0, "assume P(k) true for some $k ≥ 3$:  $C(2, 2) + … + C(k − 1, 2) = C(k, 3)$", "M1"),
        (0, "consider n = k + 1:  $C(2, 2) + … + C(k − 1, 2) + C(k, 2) = C(k, 3) + C(k, 2)$", "M1A1"),
        (0, "$= k(k − 1)(k − 2)/6 + k(k − 1)/2$", "M1A1"),
        (0, "$= k(k − 1)(k − 2 + 3)/6 = (k + 1)k(k − 1)/6$", "A1"),
        (0, "$= C(k + 1, 3)$", "A1"),
        (0, "P(3) is true and P(k) true ⇒ P(k + 1) true, so P(n) is true for all $n ∈ ℤ, n ≥ 3$", "R1"),
        ("NOTE", "Pascal's rule C(k, 3) + C(k, 2) = C(k + 1, 3) may be quoted: award M1A1A1A1 for it. "
                 "Award R1 only if at least four of the previous marks have been awarded."),
    ])],
    9: [("(a)", 8, [
        ("SKETCH", "q9"),
        (0, "(i)  U-shaped parabola, symmetric about the y-axis", "A1"),
        (1, "x-intercepts $(±a, 0)$ and minimum point $(0, −a²)$", "A1"),
        (0, "(ii)  vertical asymptotes $x = ±a$", "A1"),
        (1, "horizontal asymptote $y = 0$", "A1"),
        (1, "local maximum point $(0, −1/a²)$", "A1"),
        (1, "correct shape: positive branches for $|x| > a$, negative branch between the asymptotes", "A1"),
        (0, "(iii)  middle branch reflected in the x-axis, outer branches unchanged", "A1"),
        (1, "local minimum point $(0, 1/a²)$", "A1"),
    ]), ("(b)", 5, [
        (0, "$∫ (x² − a²) cos x dx$:  attempt integration by parts", "M1"),
        (0, "$= (x² − a²) sin x − ∫ 2x sin x dx$", "A1"),
        (0, "second integration by parts", "M1"),
        (0, "$∫ 2x sin x dx = −2x cos x + 2 sin x$", "A1"),
        (0, "$∫ f(x) cos x dx = (x² − a² − 2) sin x + 2x cos x + c$", "A1"),
        ("NOTE", "Accept equivalent forms."),
    ]), ("(c)", 4, [
        (0, "$g′(x) = √(x² − a²) + x · x/√(x² − a²)$", "M1A1"),
        (0, "$= (2x² − a²)/√(x² − a²)$", "A1"),
        (0, "for $|x| > a$: $x² > a²$ so $2x² − a² > a² > 0$, and $√(x² − a²) > 0$; "
            "hence $g′(x) > 0$ and g is increasing", "R1"),
    ])],
    10: [("(a)", 9, [
        (0, "(i)  $P = 2r + 2h + πr$, where h is the height of the rectangle", "(M1)"),
        (1, "$h = (P − 2r − πr)/2$", "A1"),
        (1, "$A = 2rh + ½πr²$", "(M1)"),
        (1, "$A = r(P − 2r − πr) + ½πr² = Pr − 2r² − ½πr²$", "A1"),
        (0, "(ii)  $dA/dr = P − 4r − πr$", "M1A1"),
        (1, "$P − (4 + π)r = 0  ⇒  r = P/(4 + π)$", "M1"),
        (1, "width $= 2r = 2P/(4 + π)$", "A1"),
        (1, "$d²A/dr² = −(4 + π) < 0$, so the area is a maximum", "R1"),
    ]), ("(b)", 2, [
        (0, "$h = (P − (2 + π)r)/2$ with $P = (4 + π)r$", "M1"),
        (0, "$h = ((4 + π)r − (2 + π)r)/2 = r$", "A1"),
        (0, "", "AG"),
    ])],
    11: [("(a)", 5, [
        (0, "$2(sin x cos 60° + cos x sin 60°) = cos x cos 30° − sin x sin 30°$", "M1"),
        (0, "$sin x + √3 cos x = (√3/2) cos x − ½ sin x$", "A1"),
        (0, "$(3/2) sin x = −(√3/2) cos x$", ""),
        (0, "$tan x = −1/√3$", "M1A1"),
        (0, "$x = 150°$", "A1"),
        ("NOTE", "Award the final A0 if extra solutions outside 0° ≤ x ≤ 180° are given."),
    ]), ("(b)", 3, [
        ("METHOD", "METHOD 1"),
        (0, "$sin 105° = sin(60° + 45°) = (√6 + √2)/4$", "M1A1"),
        (0, "$cos 105° = cos(60° + 45°) = (√2 − √6)/4$", "A1"),
        (0, "$sin 105° + cos 105° = 2√2/4 = 1/√2$", "AG"),
        ("METHOD", "METHOD 2"),
        (0, "$sin 105° + cos 105° = √2 sin(105° + 45°)$", "M1A1"),
        (0, "$= √2 sin 150° = √2/2$", "A1"),
        (0, "$= 1/√2$", "AG"),
    ]), ("(c)", 14, [
        (0, "(i)  $1 − cos 2θ = 2 sin²θ$,  $sin 2θ = 2 sin θ cos θ$", "M1"),
        (1, "$z = 2 sin²θ − 2i sin θ cos θ$", "A1"),
        (1, "$= 2 sin θ (sin θ − i cos θ)$", "A1"),
        (1, "$= 2 sin θ (cos(θ − π/2) + i sin(θ − π/2))$", "M1A1"),
        (1, "since $sin θ ≥ 0$ for $0 ≤ θ ≤ π$:", "R1"),
        (1, "$|z| = 2 sin θ$", "A1"),
        (1, "$arg z = θ − π/2$", "A1"),
        ("NOTE", "z = 0 when θ = 0 or θ = π, and its argument is then undefined."),
        (0, "(ii)  $w³ = z$:  $w = ∛(2 sin θ) cis((θ − π/2 + 2kπ)/3)$, $k = 0, 1, 2$", "M1"),
        (1, "modulus $∛(2 sin θ)$", "A1"),
        (1, "$w₀ = ∛(2 sin θ) cis(θ/3 − π/6)$", "A1"),
        (1, "$w₁ = ∛(2 sin θ) cis(θ/3 + π/2)$", "M1A1"),
        (1, "$w₂ = ∛(2 sin θ) cis(θ/3 + 7π/6)$", "A1"),
        ("NOTE", "Accept arguments that differ by multiples of 2π, e.g. θ/3 − 5π/6 for w₂."),
    ])],
}

# part marks as printed on the question paper (read from the question images)
STATED = {1: [5], 2: [2, 2, 2], 3: [4, 1], 4: [5, 2], 5: [4], 6: [4, 3], 7: [3, 4], 8: [9],
          9: [8, 5, 4], 10: [9, 2], 11: [5, 3, 14]}


def mark_value(code):
    """'M1A1' -> 2, '(M1)' -> 1, 'A1FT' -> 1, 'AG' -> 0, 'A2' -> 2."""
    return sum(int(v) for v in re.findall(r"[MARN](\d)", code.replace("AG", "")))


def part_marks(lines):
    """Marks of a part; with alternatives, each METHOD must total the same and count once."""
    groups, cur = [], []
    for ln in lines:
        if ln[0] == "METHOD":
            if cur:
                groups.append(cur)
            cur = []
        elif isinstance(ln[0], int):
            cur.append(mark_value(ln[2]))
    groups.append(cur)
    totals = [sum(g) for g in groups if g]
    assert len(set(totals)) == 1, f"alternative methods carry different marks: {totals}"
    return totals[0]


def check_marks(db_marks):
    for q, parts in SCHEMES.items():
        got = [part_marks(lines) for _, _, lines in parts]
        stated = [s for _, s, _ in parts]
        assert stated == STATED[q], f"Q{q}: scheme part marks {stated} != paper {STATED[q]}"
        assert got == stated, f"Q{q}: marks per part {got} != stated {stated}"
        assert sum(got) == db_marks[q], f"Q{q}: total {sum(got)} != [Maximum mark: {db_marks[q]}]"
    print("  mark totals: every part matches the paper and every question matches its maximum mark")


# ---------------------------------------------------------------------------------------
# Rendering (200 dpi equivalent, same width as the scanned scheme crops)
# ---------------------------------------------------------------------------------------
W = 1495
SUP = "/System/Library/Fonts/Supplemental/"
F_TEXT = ImageFont.truetype(SUP + "Arial.ttf", 31)
F_MATH = ImageFont.truetype(SUP + "STIXTwoText.ttf", 34)
F_MARK = ImageFont.truetype(SUP + "Arial Bold Italic.ttf", 31)
F_LABEL = ImageFont.truetype(SUP + "Arial Bold.ttf", 31)
F_NOTE = ImageFont.truetype(SUP + "Arial.ttf", 28)
F_NOTE_B = ImageFont.truetype(SUP + "Arial Bold.ttf", 28)
F_BANNER = ImageFont.truetype(SUP + "Arial Bold.ttf", 30)
F_BANNER_S = ImageFont.truetype(SUP + "Arial.ttf", 26)
F_SMALL = ImageFont.truetype(SUP + "STIXTwoText-Italic.ttf", 26)

INK = (25, 25, 25)
AMBER_FILL, AMBER_EDGE, AMBER_INK = (255, 236, 179), (196, 128, 18), (110, 62, 0)
X_LABEL, X_TEXT, X_MARK = 40, 200, W - 50
INDENT = 70
LINE_H = 58
TEXT_W = X_MARK - 230


F_MATH_FALLBACK = [F_MATH, ImageFont.truetype(SUP + "STIXGeneral.otf", 34),
                   ImageFont.truetype(SUP + "Arial Unicode.ttf", 31)]
F_TEXT_FALLBACK = [F_TEXT, ImageFont.truetype(SUP + "Arial Unicode.ttf", 31)]
F_SCRIPT = [ImageFont.truetype(SUP + "STIXTwoText.ttf", 24), ImageFont.truetype(SUP + "STIXGeneral.otf", 24),
            ImageFont.truetype(SUP + "Arial Unicode.ttf", 22)]
_NOTDEF = {}


def has_glyph(font, ch):
    """PIL draws .notdef (a box) for missing glyphs; compare against a private-use char's box."""
    if ch.isspace():
        return True
    key = id(font)
    if key not in _NOTDEF:
        _NOTDEF[key] = bytes(font.getmask("\uE000"))
    return bytes(font.getmask(ch)) != _NOTDEF[key]


def font_runs(text, chain):
    """Split text into runs, each drawn in the first font of `chain` that has the glyphs."""
    runs = []
    for ch in text:
        f = next((f for f in chain if has_glyph(f, ch)), chain[-1])
        if runs and runs[-1][0] is f:
            runs[-1][1] += ch
        else:
            runs.append([f, ch])
    return runs


def tokens(text):
    """Prose/maths tokens: [(font, text, dy)]. In maths, ^{…} is a superscript and _{…} a
    subscript; words keep their spaces as separate tokens so wrapping works."""
    out = []
    for i, seg in enumerate(re.split(r"\$", text)):
        if i % 2 == 0:
            for w in re.split(r"( +)", seg):
                if w:
                    for f, run in font_runs(w, F_TEXT_FALLBACK):
                        out.append((f, run, 0))
            continue
        for part in re.split(r"([\^_]\{[^}]*\})", seg):
            if not part:
                continue
            if part[0] in "^_" and part[1:2] == "{":
                dy = -14 if part[0] == "^" else 12
                for f, run in font_runs(part[2:-1], F_SCRIPT):
                    out.append((f, run, dy))
                continue
            for w in re.split(r"( +)", part):
                if w:
                    for f, run in font_runs(w, F_MATH_FALLBACK):
                        out.append((f, run, 0))
    return out


def wrap(text, width):
    lines, cur, cw = [], [], 0
    for tok in tokens(text):
        font, w, _ = tok
        tw = font.getlength(w)
        if w.isspace() and not cur:
            continue
        if cw + tw > width and cur and not w.isspace():
            lines.append(cur)
            cur, cw = [], 0
        cur.append(tok)
        cw += tw
    if cur:
        lines.append(cur)
    return lines or [[]]


def row(height):
    return Image.new("RGB", (W, height), "white")


BASE = 12 + F_TEXT.getmetrics()[0]          # common baseline for prose, maths and fallback glyphs
NOTE_BASE = F_NOTE.getmetrics()[0]


def text_rows(label, indent, text, code):
    x0 = X_TEXT + indent * INDENT
    rows = []
    for i, ln in enumerate(wrap(text, TEXT_W - indent * INDENT)):
        im = row(LINE_H)
        d = ImageDraw.Draw(im)
        if i == 0 and label:
            d.text((X_LABEL, 12), label, font=F_LABEL, fill=INK)
        x = x0
        for font, w, dy in ln:
            d.text((x, BASE - font.getmetrics()[0] + dy), w, font=font, fill=INK)
            x += font.getlength(w)
        rows.append(im)
    if code:
        d = ImageDraw.Draw(rows[-1])
        d.text((X_MARK - F_MARK.getlength(code), 12), code, font=F_MARK, fill=INK)
    return rows


def note_rows(text):
    box_x0, box_x1 = X_TEXT - 10, X_MARK - 200
    lines = wrap("Note:  " + text, (box_x1 - box_x0) - 50)      # fits inside the box
    h = 22 + 44 * len(lines)
    im = row(h + 20)
    d = ImageDraw.Draw(im)
    d.rectangle([box_x0, 10, box_x1, 10 + h], outline=INK, width=2)
    y = 20
    for ln in lines:
        x = X_TEXT + 6
        for font, w, dy in ln:
            f = F_NOTE_B if w.startswith("Note:") else (F_NOTE if font is F_TEXT else font)
            d.text((x, y + NOTE_BASE - f.getmetrics()[0] + dy), w, font=f, fill=INK)
            x += f.getlength(w)
        y += 44
    return [im]


def method_rows(text):
    im = row(LINE_H + 10)
    ImageDraw.Draw(im).text((X_TEXT, 22), text, font=F_LABEL, fill=INK)
    return [im]


def marks_row(text, bold_total=False):
    im = row(LINE_H)
    f = F_MARK
    ImageDraw.Draw(im).text((X_MARK - f.getlength(text), 10), text, font=f, fill=INK)
    return [im]


def sketch_q9():
    """Three sketches for Q9(a) drawn with a = 1, labelled in terms of a."""
    pw, ph, gap = 400, 380, 40
    im = row(ph + 60)
    d = ImageDraw.Draw(im)
    panels = [
        ("(i)  y = f(x)", lambda v: v * v - 1, (-1.6, 4.0), [], [(-1, 0, "−a"), (1, 0, "a"), (0, -1, "−a²")]),
        ("(ii)  y = 1/f(x)", lambda v: 1 / (v * v - 1), (-3.2, 3.2), [-1, 1], [(0, -1, "−1/a²")]),
        ("(iii)  y = |1/f(x)|", lambda v: abs(1 / (v * v - 1)), (-0.8, 3.6), [-1, 1], [(0, 1, "1/a²")]),
    ]
    for i, (title, fn, (ylo, yhi), asym, pts) in enumerate(panels):
        ox = X_TEXT + i * (pw + gap)
        top = 50
        X = lambda v: ox + (v + 2.6) / 5.2 * pw
        Y = lambda v: top + (yhi - v) / (yhi - ylo) * ph
        d.text((ox, 6), title, font=F_SMALL, fill=INK)
        d.line([(X(-2.6), Y(0)), (X(2.6), Y(0))], fill=INK, width=2)               # x-axis
        d.line([(X(0), Y(ylo)), (X(0), Y(yhi))], fill=INK, width=2)               # y-axis
        d.text((X(2.6) - 16, Y(0) + 4), "x", font=F_SMALL, fill=INK)
        d.text((X(0) + 6, Y(yhi) - 2), "y", font=F_SMALL, fill=INK)
        for xa in asym:                                                           # dashed asymptotes
            for yy in range(int(Y(yhi)), int(Y(ylo)), 14):
                d.line([(X(xa), yy), (X(xa), yy + 7)], fill=INK, width=2)
        seg, v = [], -2.5
        while v <= 2.5:
            yv = None
            if not any(abs(v - xa) < 0.04 for xa in asym):
                yv = fn(v)
            if yv is None or not (ylo <= yv <= yhi):
                if len(seg) > 1:
                    d.line(seg, fill=INK, width=4)
                seg = []
            else:
                seg.append((X(v), Y(yv)))
            v += 0.01
        if len(seg) > 1:
            d.line(seg, fill=INK, width=4)
        for px, py, lab in pts:
            d.ellipse([X(px) - 5, Y(py) - 5, X(px) + 5, Y(py) + 5], fill=INK)
            dx = 8 if px >= 0 else -8 - F_SMALL.getlength(lab)
            dy = 6 if py <= 0 else -34
            if px == 0:      # on the y-axis: label to its right, on the open side of the turning point
                dx = 10
                dy = 6 if fn(0.0) < fn(0.3) else -36      # below a minimum, above a maximum
            tx, ty = X(px) + dx, Y(py) + dy
            tw = F_SMALL.getlength(lab)
            d.rectangle([tx - 3, ty + 4, tx + tw + 3, ty + 32], fill="white")   # halo
            d.text((tx, ty), lab, font=F_SMALL, fill=INK)
        for xa in asym:
            lab = "a" if xa > 0 else "−a"
            d.text((X(xa) + (6 if xa > 0 else -6 - F_SMALL.getlength(lab)), Y(0) + 4), lab, font=F_SMALL, fill=INK)
    return [im]


SKETCHES = {"q9": sketch_q9}


def banner(q, part_of):
    im = row(118)
    d = ImageDraw.Draw(im)
    d.rectangle([12, 10, W - 12, 108], fill=AMBER_FILL, outline=AMBER_EDGE, width=4)
    d.text((34, 22), "UNOFFICIAL MARK SCHEME — worked by Claude, not an IB document",
           font=F_BANNER, fill=AMBER_INK)
    sub = f"{LABEL} · Question {q}" + (f" · part {part_of[0]} of {part_of[1]}" if part_of[1] > 1 else "")
    d.text((34, 66), sub + " · results verified with sympy", font=F_BANNER_S, fill=AMBER_INK)
    return im


def render_question(q):
    parts = SCHEMES[q]
    rows = []
    for pi_, (label, stated, lines) in enumerate(parts):
        # the label ("11.", "11.  (a)", "(b)") is drawn on the first row the part produces
        pending = " ".join(x for x in ((f"{q}." if pi_ == 0 else ""), label or "") if x)
        for ln in lines:
            kind = ln[0]
            if kind == "NOTE":
                new = note_rows(ln[1])
            elif kind == "METHOD":
                new = method_rows(ln[1])
            elif kind == "SKETCH":
                new = ([row(LINE_H)] if pending else []) + SKETCHES[ln[1]]()
            else:
                new = text_rows(None, *ln)
            if pending and kind != "NOTE":
                ImageDraw.Draw(new[0]).text((X_LABEL, 12 if kind != "METHOD" else 22), pending,
                                            font=F_LABEL, fill=INK)
                pending = ""
            rows += new
        if len(parts) > 1:
            rows += marks_row(f"[{stated} mark{'s' if stated != 1 else ''}]")
        rows.append(row(20))
    total = sum(s for _, s, _ in parts)
    rows += marks_row(f"Total [{total} marks]")

    # chunk to the same page-height limit as the scanned crops; banner on every chunk
    limit = int(720 * 200 / 72) - 118
    chunks, cur, h = [], [], 0
    for r in rows:
        if cur and h + r.height > limit:
            chunks.append(cur)
            cur, h = [], 0
        cur.append(r)
        h += r.height
    chunks.append(cur)
    images = []
    for i, c in enumerate(chunks):
        H = 118 + sum(r.height for r in c) + 16
        canvas = Image.new("RGB", (W, H), "white")
        canvas.paste(banner(q, (i + 1, len(chunks))), (0, 0))
        y = 118
        for r in c:
            canvas.paste(r, (0, y))
            y += r.height
        d = ImageDraw.Draw(canvas)
        d.rectangle([0, 0, 7, H], fill=AMBER_EDGE)                     # amber edge stripe
        images.append(canvas)
    return images


def glyph_audit():
    missing = set()
    for parts in SCHEMES.values():
        for _, _, lines in parts:
            for ln in lines:
                text = ln[1] if ln[0] in ("NOTE", "METHOD") else (ln[1] if ln[0] != "SKETCH" else "")
                for f, run, _ in tokens(text):
                    missing |= {ch for ch in run if not has_glyph(f, ch)}
    assert not missing, f"characters with no glyph in any font: {sorted(missing)}"
    print("  glyphs: every character renders")


def main():
    glyph_audit()
    print("verifying results with sympy …")
    verify_ms.run()
    db_marks = {q["q"]: q["marks"] for q in json.loads((OUT / "extract.json").read_text())[PAPER]["questions"]}
    assert set(db_marks) == set(SCHEMES), "a scheme for every question, and only those"
    check_marks(db_marks)

    authored = {}
    for q in SCHEMES:
        stem = f"{PAPER}_ams{q:02d}"
        for old in [*(OUT / "img").glob(f"{stem}_*.webp"), *(OUT / "png").glob(f"{stem}_*.png")]:
            old.unlink()
        names = []
        for k, im in enumerate(render_question(q)):
            im.save(OUT / "png" / f"{stem}_{k}.png", optimize=True)
            im.save(OUT / "img" / f"{stem}_{k}.webp", lossless=True, quality=100, method=4)
            names.append(f"{stem}_{k}.webp")
        authored[f"{PAPER}-Q{q}"] = {
            "mi": names, "marks": db_marks[q],
            "parts": [[lab or "", s] for lab, s, _ in SCHEMES[q]],
            "verified": True,
        }
    (OUT / "authored.json").write_text(json.dumps(authored, indent=1, ensure_ascii=False))
    print(f"rendered {sum(len(v['mi']) for v in authored.values())} images for {len(authored)} questions "
          f"-> out/authored.json")


if __name__ == "__main__":
    main()
