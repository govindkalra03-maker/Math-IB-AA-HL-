"""Stage 8 — verify every deliverable, independently of the scripts that built it.

  1. database: unique ids, every referenced image exists (WebP + PNG), marks match paper totals
  2. PDFs: every question exactly once across the five PDFs (count per topic); every internal link
     resolves to a real page AND to the page it is meant to reach; every bookmark lands on its question
  3. authored mark schemes: results re-verified with sympy; marks per part sum to the paper's part
     marks and to the question total; flagged msAuthored in the db and only those
  4. dashboard (Playwright, opened from file:// exactly as a double-click would): no console errors,
     header counts match the db, searches are sane, the official-only filter drops exactly the authored
     schemes, the reader works from the keyboard, the exam generator hits its target, the printed
     paper renders (with and without mark schemes). Screenshots go to verify/.

    .venv/bin/python -I verify.py
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pymupdf

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from syllabus import TOPICS  # noqa: E402

OUT, DIST, SHOTS = HERE / "out", HERE / "dist", HERE / "verify"
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append({"check": name, "ok": bool(ok), "detail": detail})
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {detail}" if detail else ""))
    return ok


# ------------------------------------------------------------------------------------------
def verify_data(db, papers):
    print("\n[1] database and images")
    ids = [r["id"] for r in db]
    check("question ids unique", len(ids) == len(set(ids)), f"{len(ids)} records")
    refs = [f for r in db for f in r["qi"] + r["mi"]]
    missing = [f for f in refs if not (OUT / "img" / f).exists()]
    missing_png = [f for f in refs if not (OUT / "png" / f.replace(".webp", ".png")).exists()]
    local_missing = [f for f in refs if not (DIST / "local" / "img" / f.replace(".webp", ".png")).exists()]
    check("every referenced image exists on disk", not missing and not missing_png and not local_missing,
          f"{len(refs)} references, {len(set(refs))} files; missing webp {len(missing)}, png {len(missing_png)}, "
          f"local copy {len(local_missing)}")
    check("every question has a question image and a mark scheme",
          all(r["qi"] and r["mi"] for r in db))
    bad = [p["id"] for p in papers if sum(r["marks"] for r in db if r["id"].startswith(p["id"] + "-")) != p["total"]]
    check("question marks sum to each paper's printed total", not bad, f"{len(papers)} papers" + (f"; bad {bad}" if bad else ""))


# ------------------------------------------------------------------------------------------
def verify_pdfs(db):
    print("\n[2] topic PDFs")
    key = {(r["label"], r["q"]): r["id"] for r in db}
    files = sorted(DIST.glob("IB Maths AA HL - Topic *.pdf"))
    check("five topic PDFs exist", len(files) == 5, ", ".join(f.name for f in files))
    seen = Counter()
    per_topic = {}
    link_total = link_bad = target_bad = bm_bad = 0
    for f in files:
        doc = pymupdf.open(f)
        n = doc.page_count
        topic = int(re.search(r"Topic (\d)", f.name).group(1))
        toc = doc.get_toc()
        q_ids = [re.search(r"\[([^\]]+)\]$", t).group(1) for lvl, t, _ in toc if lvl == 2]
        seen.update(q_ids)
        per_topic[topic] = len(q_ids)
        toc_page = next(p - 1 for lvl, t, p in toc if t == "Contents")      # get_toc: 1-based
        for lvl, t, p in toc:
            if not 1 <= p <= n:
                bm_bad += 1
            elif lvl == 2 and re.search(r"\[([^\]]+)\]$", t).group(1) not in doc[p - 1].get_text():
                bm_bad += 1
        for page in doc:                                                   # page.number: 0-based
            for ln in page.get_links():
                if ln["kind"] not in (pymupdf.LINK_GOTO, pymupdf.LINK_NAMED):
                    continue
                link_total += 1
                tgt = ln.get("page", -1)                                   # LINK_GOTO: 0-based
                if not 0 <= tgt < n:
                    link_bad += 1
                    continue
                txt = page.get_textbox(ln["from"]).replace("\n", " ")
                m = re.search(r"(\w+ \d{4} · Paper \d(?: · TZ\d)?) · Q(\d+)", txt)
                if "back to contents" in txt and tgt != toc_page:
                    target_bad += 1
                elif m and key[(m.group(1), int(m.group(2)))] not in doc[tgt].get_text():
                    target_bad += 1
        expect = sum(1 for r in db if r["topic"] == topic)
        check(f"Topic {topic} ({TOPICS[topic]}) has every question once", len(q_ids) == expect == len(set(q_ids)),
              f"{len(q_ids)} questions, {n} pages")
    all_ids = {r["id"] for r in db}
    dup = sorted(k for k, v in seen.items() if v > 1)
    check("every db question appears exactly once across the five PDFs",
          set(seen) == all_ids and not dup, f"{sum(seen.values())} placements / {len(all_ids)} questions; "
          f"duplicates {dup or 'none'}; missing {sorted(all_ids - set(seen)) or 'none'}")
    check("every internal link resolves to a real page", link_bad == 0, f"{link_total} links, {link_bad} out of range")
    check("every contents link / back-link lands on its intended page", target_bad == 0, f"{target_bad} mis-targeted")
    check("every bookmark resolves and question bookmarks land on their question", bm_bad == 0)
    return per_topic


# ------------------------------------------------------------------------------------------
def verify_authored(db):
    print("\n[3] authored mark schemes")
    import author_ms
    import verify_ms
    try:
        verify_ms.run()
        check("all authored results re-verified symbolically (sympy)", True, f"{len(verify_ms.CHECKS)} questions")
    except AssertionError as e:
        check("all authored results re-verified symbolically (sympy)", False, repr(e))
    marks = {r["q"]: r["marks"] for r in db if r["id"].startswith(author_ms.PAPER + "-")}
    try:
        author_ms.check_marks(marks)
        check("authored marks per part = paper's part marks; per question = [Maximum mark]", True,
              f"{sum(marks.values())} marks over {len(marks)} questions")
    except AssertionError as e:
        check("authored marks per part = paper's part marks; per question = [Maximum mark]", False, str(e))
    authored = json.loads((OUT / "authored.json").read_text())
    flagged = {r["id"] for r in db if r["msAuthored"]}
    check("msAuthored is set on exactly the authored questions", flagged == set(authored),
          f"{len(flagged)} flagged")
    check("authored scheme images are separate files (_ams), never official ones",
          all(all("_ams" in f for f in r["mi"]) for r in db if r["msAuthored"]) and
          not any("_ams" in f for r in db if not r["msAuthored"] for f in r["mi"]))
    return sorted(flagged, key=lambda s: int(s.split("-Q")[1]))


# ------------------------------------------------------------------------------------------
def verify_dashboard(db, papers):
    print("\n[4] dashboard (Playwright)")
    from playwright.sync_api import sync_playwright
    SHOTS.mkdir(exist_ok=True)
    n, marks = len(db), sum(r["marks"] for r in db)
    n_auth = sum(r["msAuthored"] for r in db)
    url = (DIST / "HL Paper Lab.html").resolve().as_uri()
    errors = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1360, "height": 900}, color_scheme="light")
        page = ctx.new_page()
        page.on("console", lambda m: m.type == "error" and errors.append(m.text))
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(url)
        page.wait_for_selector("#list .row", timeout=60000)

        stats = page.text_content("#stats")
        check("header counts match the database",
              stats == f"{n} questions · {marks:,} marks · {len(papers)} papers", stats)
        rows = page.locator("#list .row").count()
        rc = page.text_content("#resultCount")
        check("initial list shows every question", rows == n and f"{n} questions" in rc and f"{marks:,} marks" in rc, rc)
        all_imgs = page.evaluate("""() => DB.every(r => r.qi.concat(r.mi).every(f => (imgSrc(f) || '').startsWith('data:image/webp;base64,')))""")
        check("every image is embedded as a data: URI in the single file", all_imgs)
        page.screenshot(path=str(SHOTS / "01-bank-light.png"))

        # search sanity: displayed results = db records whose text contains the term; all relevant
        def search(term):
            page.fill("#q", term)
            page.wait_for_timeout(250)
            shown = page.eval_on_selector_all("#list .row", "els => els.map(e => e.dataset.id)")
            return shown
        for term, needle in [("Maclaurin", "maclaurin"), ("De Moivre", "de moivre"), ("Bayes", "bayes")]:
            shown = search(term)
            expect = {r["id"] for r in db if needle in " ".join([r["desc"], r["sub"], r["code"], r["label"], r["id"]]).lower()}
            check(f"search '{term}' returns exactly the matching questions", set(shown) == expect and shown,
                  f"{len(shown)} results")
        search("M25P1TZ2-Q11")
        check("search by question id finds that question", page.locator("#list .row").count() == 1)
        search("integration by parts volume")
        multi = page.eval_on_selector_all("#list .row", "els => els.map(e => e.innerText.toLowerCase())")
        check("multi-word search requires every word", all("volume" in t for t in multi), f"{len(multi)} results")
        search("")

        # official-only filter removes exactly the authored schemes
        before = page.locator("#list .row").count()
        page.check("#officialOnly")
        page.wait_for_timeout(150)
        after = page.locator("#list .row").count()
        amber = page.locator("#list .tag.amber").count()
        check("'official mark scheme only' reduces the count by exactly the authored schemes",
              before - after == n_auth and amber == 0, f"{before} -> {after} (−{before - after}; {n_auth} authored)")
        page.uncheck("#officialOnly")

        # topic facet + live counts
        page.check('input[data-facet="topics"][value="5"]')
        page.wait_for_timeout(150)
        t5 = sum(1 for r in db if r["topic"] == 5)
        check("topic filter matches the database", page.locator("#list .row").count() == t5, f"Calculus: {t5}")
        sub_counts = page.eval_on_selector_all("#f-subs .opt", "els => els.map(e => +e.querySelector('.count').textContent)")
        check("sub-topic live counts sum to the filtered total", sum(sub_counts) == t5)
        page.click("#resetFilters")

        # sorting
        page.select_option("#sort", "marksDesc")
        top = page.eval_on_selector_all("#list .row .marks", "els => els.slice(0, 50).map(e => +e.textContent)")
        check("sort by marks (high to low) is ordered", top == sorted(top, reverse=True) and top[0] == max(r["marks"] for r in db))
        page.select_option("#sort", "newest")

        # reader, keyboard only
        page.focus("#list .row")
        page.keyboard.press("Enter")
        page.wait_for_selector("#reader:not([hidden])")
        page.keyboard.press("m")
        page.wait_for_timeout(300)
        ms_ok = page.evaluate("() => [...document.querySelectorAll('#msArea img')].every(i => i.complete && i.naturalWidth > 0) && document.querySelectorAll('#msArea img').length > 0")
        page.keyboard.press("ArrowRight")
        pos = page.text_content("#rdPos")
        page.screenshot(path=str(SHOTS / "02-reader.png"))
        page.keyboard.press("Escape")
        page.wait_for_timeout(100)
        check("reader opens from the keyboard, shows the mark scheme, steps, and closes on Escape",
              ms_ok and pos.startswith("2 /") and page.is_hidden("#reader"), pos)

        # an authored question in the reader
        search("M17P1TZ2-Q9")
        page.click("#list .row")
        btn = page.text_content("#msBtn").strip()
        page.click("#msBtn")
        page.wait_for_timeout(300)
        amber_head = page.locator(".ms-head.amber").count()
        page.screenshot(path=str(SHOTS / "03-reader-authored.png"))
        page.keyboard.press("Escape")
        check("authored schemes read 'Show worked solution' with an amber unofficial notice",
              btn == "Show worked solution" and amber_head == 1)
        search("")

        # dark theme
        page.click("#themeBtn")
        page.wait_for_timeout(100)
        dark_bg = page.evaluate("() => getComputedStyle(document.body).backgroundColor")
        page.screenshot(path=str(SHOTS / "04-bank-dark.png"))
        page.click("#themeBtn")
        check("theme toggle switches to the dark palette", dark_bg == "rgb(17, 19, 23)", dark_bg)

        # mock exam generator: every preset, several times
        page.click("#tab-exam")
        results = []
        for target in (40, 55, 110, 220, 73):
            for _ in range(3):
                if target in (40, 55, 110, 220):
                    page.click(f'#exPresets button[data-v="{target}"]')
                else:
                    page.fill("#exTarget", str(target)); page.dispatch_event("#exTarget", "change")
                page.click("#generate")
                total = page.evaluate("() => [...EXAM.keys()].reduce((s, id) => s + BY_ID.get(id).marks, 0)")
                shown = int(page.text_content("#exTotal").split()[0])
                results.append((target, total, shown))
        hits = [t == tot == s for t, tot, s in results]
        check("exam generator hits its target", all(hits),
              ", ".join(sorted({f"{t}→{tot}" for t, tot, _ in results}, key=lambda x: int(x.split('→')[0]))))
        order_ok = page.evaluate("""() => { const {A, B} = examOrder();
            return A.every((r, i) => !i || A[i-1].marks <= r.marks) && B.every((r, i) => !i || B[i-1].marks <= r.marks)
                   && A.every(r => r.section === 'A') && B.every(r => r.section === 'B'); }""")
        nums = page.eval_on_selector_all("#paperWrap .pq-num", "els => els.map(e => e.textContent)")
        check("paper is arranged Section A (ascending) then Section B, renumbered 1, 2, 3 …",
              order_ok and nums == [f"{i}." for i in range(1, len(nums) + 1)], f"{len(nums)} questions")
        dup_mm = page.evaluate("() => document.querySelector('#paperWrap .sec-a, #paperWrap .sec-b').innerText.includes('Maximum mark')")
        check("the exam header does not repeat [Maximum mark] (it is in the image)", not dup_mm)

        # dropping a question updates the total live
        page.click('#exPresets button[data-v="110"]')
        page.click("#generate")
        first_marks = int(page.text_content("#selList .sel-row .marks"))
        page.click("#selList .drop")
        new_total = int(page.text_content("#exTotal").split()[0])
        fit = page.text_content("#exFit")
        check("× drops a question and the total updates live", new_total == 110 - first_marks and "under" in fit,
              f"110 − {first_marks} = {new_total}; tag '{fit}'")
        page.click("#generate")
        page.screenshot(path=str(SHOTS / "05-exam.png"))
        page.locator("#paperWrap .sheet.cover").screenshot(path=str(SHOTS / "06-paper-cover.png"))

        # printed paper (print CSS) with and without mark schemes
        page.emulate_media(media="print")
        pdf = page.pdf(format="A4", print_background=True)
        (SHOTS / "07-mock-paper.pdf").write_bytes(pdf)
        page.evaluate("() => document.body.classList.add('print-ms')")
        pdf_ms = page.pdf(format="A4", print_background=True)
        (SHOTS / "08-mock-paper-with-ms.pdf").write_bytes(pdf_ms)
        page.evaluate("() => document.body.classList.remove('print-ms')")
        page.emulate_media(media="screen")
        d1, d2 = pymupdf.open(stream=pdf, filetype="pdf"), pymupdf.open(stream=pdf_ms, filetype="pdf")
        t1 = " ".join(p.get_text() for p in d1)
        t2 = " ".join(p.get_text() for p in d2)
        n_imgs = sum(len(p.get_images()) for p in d1)
        check("printed paper renders: cover, instructions, sections, question images; UI hidden",
              "Instructions to candidates" in t1 and "Section A" in t1 and "[110 marks]" in t1 and n_imgs >= 10
              and "Question bank" not in t1 and "Generate paper" not in t1 and "Mark scheme" not in t1,
              f"{d1.page_count} A4 pages, {n_imgs} images")
        check("'print with mark schemes' appends the schemes", d2.page_count > d1.page_count and "Mark scheme" in t2,
              f"{d2.page_count} pages")
        for i in (0, 1):
            d1[i].get_pixmap(dpi=70).save(str(SHOTS / f"09-printed-page-{i + 1}.png"))

        # local copy with separate PNGs
        lp = ctx.new_page()
        lp.on("pageerror", lambda e: errors.append("local: " + str(e)))
        lp.goto((DIST / "local" / "index.html").resolve().as_uri())
        lp.wait_for_selector("#list .row", state="attached")   # the app restores the last-used tab
        lp.click("#tab-bank")
        lp.click("#list .row")
        lp.wait_for_timeout(500)
        loaded = lp.evaluate("() => { const i = document.querySelector('#rdBody img'); return i && i.complete && i.naturalWidth; }")
        check("local copy (dist/local/index.html) loads and shows PNG images", loaded and loaded > 1000, f"width {loaded}px")
        browser.close()
    check("dashboard loads with no console errors", not errors, "; ".join(errors[:5]) or "0 errors")


# ------------------------------------------------------------------------------------------
def summary(db, papers, per_topic, authored):
    print("\n[report] totals")
    print(f"  {len(db)} questions, {sum(r['marks'] for r in db)} marks, {len(papers)} papers")
    print("  per topic:")
    for t, name in TOPICS.items():
        rs = [r for r in db if r["topic"] == t]
        print(f"    Topic {t} {name:28} {len(rs):4} questions {sum(r['marks'] for r in rs):5} marks   (PDF: {per_topic.get(t)})")
    print("  per session:")
    by = defaultdict(list)
    for r in db:
        by[(r["year"], r["session"])].append(r)
    for (y, s), rs in sorted(by.items(), key=lambda kv: (-kv[0][0], kv[0][1] != "November")):
        pp = sorted({r["label"].replace(f"{s} {y} · ", "") for r in rs})
        print(f"    {s:8} {y}  {len(rs):3} questions {sum(r['marks'] for r in rs):4} marks   {', '.join(pp)}")
    print(f"  authored mark schemes: {', '.join(authored)}")


def main():
    db = json.loads((OUT / "db.json").read_text())
    papers = json.loads((HERE / "papers.json").read_text())
    verify_data(db, papers)
    per_topic = verify_pdfs(db)
    authored = verify_authored(db)
    verify_dashboard(db, papers)
    summary(db, papers, per_topic, authored)
    failed = [r for r in RESULTS if not r["ok"]]
    SHOTS.mkdir(exist_ok=True)
    (SHOTS / "report.json").write_text(json.dumps(RESULTS, indent=1, ensure_ascii=False))
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed" + (f"; FAILED: {[f['check'] for f in failed]}" if failed else ""))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
