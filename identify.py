"""Stage 1 — identify every past paper from its internal content, not its filename.

Reads the top-level PDFs in the papers folder, works out what each one is from the
cover (barcode / paper code, session line, paper number, level, language), drops the
ones we don't want, pairs each question paper with its mark scheme, collapses genuine
duplicates, and writes papers.json plus identify_report.json.

    .venv/bin/python -I identify.py [papers_dir]
"""
import difflib
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

import pymupdf

HERE = Path(__file__).resolve().parent
# folder of past-paper PDFs: command-line argument, else IB_PAPERS_DIR, else the default below
SRC = Path(sys.argv[1] if len(sys.argv) > 1 else
           os.environ.get("IB_PAPERS_DIR", "~/Downloads/School/Math/Past Papers")).expanduser()

MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
SESSION_BY_PREFIX = {"22": "May", "88": "November"}   # first two digits of the barcode


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def flat(text):
    return re.sub(r"\s+", " ", text)


def cover_info(doc):
    """Pull identifying fields from the first three pages (cover may sit behind a copyright page)."""
    t = flat(" ".join(doc[i].get_text() for i in range(min(3, doc.page_count))))
    info = {"is_ms": bool(re.search(r"\bMarkscheme\b", t[:600]))}

    code = re.search(r"/5/(\w+)/[HS]P\d/", t, re.I)
    if (code and code.group(1).upper() == "FURMA") or re.search(r"Further mathematics\s+Higher level", t):
        info["subject"] = "further"
    elif re.search(r"analysis and approaches|Análisis y Enfoques|analyse et approches", t, re.I):
        info["subject"] = "AA"
    elif (code and code.group(1).upper() == "MATHL") or re.search(r"\bMathematics\s+Higher level", t):
        info["subject"] = "maths"          # pre-2019 Mathematics HL
    else:
        info["subject"] = "?"

    info["lang"] = "es" if re.search(r"\bPrueba\b|páginas|Nivel Superior", t) else (
        "fr" if re.search(r"\bÉpreuve\b|Niveau supérieur", t) else "en")
    info["level"] = "HL" if re.search(r"Higher level|Nivel Superior|Niveau supérieur", t) else (
        "SL" if re.search(r"Standard level|Nivel Medio|Niveau moyen", t) else "?")
    m = re.search(r"\b(?:Paper|Prueba|Épreuve) (\d)\b", t)
    info["paper"] = int(m.group(1)) if m else None

    m = re.search(r"\b(\d{4}) ?[–-] ?(\d{4})(M?)\b", t)
    info["barcode"] = f"{m.group(1)}-{m.group(2)}" if m else None

    m = re.search(r"\b([MN])(\d\d)/5/(\w+)/([HS])P(\d)/(\w+)/TZ(\d)", t, re.I)
    info["code"] = None
    if m:
        g = [x.upper() for x in m.groups()]
        info["code"] = f"{g[0]}{g[1]}/5/{g[2]}/{g[3]}P{g[4]}/{g[5]}/TZ{g[6]}"
        info["code_session"] = "May" if m.group(1).upper() == "M" else "November"
        info["code_year"] = 2000 + int(m.group(2))
        info["code_tz"] = int(m.group(7))

    m = re.search(r"(?:(\d{1,2}) )?(" + MONTHS + r") (20\d\d)", t)
    info["date_line"] = m.group(0) if m else None
    info["date_month"], info["date_year"] = (m.group(2), int(m.group(3))) if m else (None, None)
    info["zones"] = "".join(a + b[0] for a, b in re.findall(r"Zon[ea] ([ABC]) +(\w+)", t))
    return info


def session_of(info):
    """(session, year) — barcode prefix first, then paper code, then the cover date line."""
    bc = info.get("barcode")
    if bc and bc[:2] in SESSION_BY_PREFIX:
        return SESSION_BY_PREFIX[bc[:2]], 2000 + int(bc[2:4])
    if info.get("code"):
        return info["code_session"], info["code_year"]
    if info["date_month"]:
        # November-session papers are sometimes sat in late October
        return ("November" if info["date_month"] in ("October", "November") else "May"), info["date_year"]
    return None, None


def body_text(doc, is_ms):
    """Text of the paper proper, for duplicate comparison and mark extraction."""
    pages = [doc[i].get_text() for i in range(doc.page_count)]
    return "\n".join(pages)


def qp_marks(text):
    return [int(x) for x in re.findall(r"\[\s*Maximum mark:\s*(\d+)\s*\]", text)]


def ms_totals(text):
    return [int(x) for x in re.findall(r"Total\s*\[\s*(\d+)\s*marks?\s*\]", text, re.I)]


def qp_parts(text):
    """Per-part marks as printed in the right margin of a question paper: "[3]"."""
    return [int(x) for x in re.findall(r"(?m)^\s*\[(\d{1,2})\]\s*$", text)]


def ms_parts(text):
    """Per-part marks in a scheme: "[3 marks]", but not the "Total [N marks]" lines."""
    return [int(m.group(1)) for m in re.finditer(r"(?<!Total )\[\s*(\d{1,2})\s*marks?\s*\]", text)
            if not re.search(r"Total\s*$", text[max(0, m.start() - 12):m.start()])]


def parts_score(a, b):
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio() if a and b else 0.0


def norm_for_compare(text):
    """Strip barcodes, page furniture and glyph noise so two printings of one paper compare equal."""
    t = re.sub(r"\b\d{4} ?[–-] ?\d{4}M?\b", " ", text)
    t = re.sub(r"\b\d\dEP\d\d\b", " ", t)
    t = re.sub(r"[MN]\d\d/5/\S+", " ", t)
    t = re.sub(r"(?i)\b(\d{1,2} )?(" + MONTHS + r") 20\d\d\b", " ", t)
    t = re.sub(r"(?i)zone [abc] +\w+", " ", t)
    t = re.sub(r"(?i)candidate session number|turn over|do not write solutions on this page", " ", t)
    t = re.sub(r"[^A-Za-z0-9]+", "", t).lower()
    return t


def tokens(text):
    """Distinctive tokens (numbers, longer words) for checking a QP and an MS belong together."""
    t = re.sub(r"\b\d{4} ?[–-] ?\d{4}M?\b|\b\d\dEP\d\d\b", " ", text)
    return set(re.findall(r"[A-Za-z]{6,}|\d+\.\d+|\b\d{2,}\b", t.lower()))


def overlap(q, m):
    return len(q & m) / max(1, len(q))


def similarity(a, b):
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def main():
    files = sorted(p for p in SRC.iterdir() if p.is_file() and not p.name.startswith("."))
    report = {"source": str(SRC), "skipped_non_pdf": [], "unreadable": [], "excluded": [],
              "byte_duplicates": [], "content_duplicates": [], "unpaired_qp": [], "unpaired_ms": [],
              "mark_mismatch": [], "notes": []}

    recs = []
    for p in files:
        if p.suffix.lower() != ".pdf":
            report["skipped_non_pdf"].append(p.name)
            continue
        try:
            doc = pymupdf.open(p)
            info = cover_info(doc)
            text = body_text(doc, info["is_ms"])
        except Exception as e:                      # never skip silently
            report["unreadable"].append({"file": p.name, "error": repr(e)})
            continue
        info.update(file=p.name, pages=doc.page_count, sha=sha(p))
        info["session"], info["year"] = session_of(info)
        info["marks"] = ms_totals(text) if info["is_ms"] else qp_marks(text)
        info["_norm"] = norm_for_compare(text)
        info["_tok"] = tokens(text)
        info["_parts"] = ms_parts(text) if info["is_ms"] else qp_parts(text)
        recs.append(info)

    # ---- exclusions -----------------------------------------------------------
    keep = []
    for r in recs:
        why = None
        if r["subject"] == "further":
            why = "Further Mathematics"
        elif r["lang"] != "en":
            why = f"non-English ({r['lang']})"
        elif r["level"] != "HL":
            why = f"level {r['level']}"
        elif r["paper"] == 3:
            why = "Paper 3"
        elif r["subject"] not in ("AA", "maths"):
            why = "unrecognised subject"
        elif r["paper"] not in (1, 2) or not r["session"]:
            why = "could not read paper number / session from cover"
        if why:
            report["excluded"].append({"file": r["file"], "reason": why, "barcode": r["barcode"],
                                       "code": r["code"], "date": r["date_line"]})
        else:
            keep.append(r)

    # ---- byte-identical copies --------------------------------------------------
    def pref(name):                                   # prefer the cleanest filename
        return (bool(re.search(r"\(\d\)| copy| \d\.pdf$", name)), len(name), name)

    by_sha = defaultdict(list)
    for r in keep:
        by_sha[r["sha"]].append(r)
    uniq = []
    for group in by_sha.values():
        group.sort(key=lambda r: pref(r["file"]))
        uniq.append(group[0])
        if len(group) > 1:
            report["byte_duplicates"].append({"kept": group[0]["file"], "dropped": [g["file"] for g in group[1:]]})

    qps = [r for r in uniq if not r["is_ms"]]
    mss = [r for r in uniq if r["is_ms"]]

    # ---- time zone for each document ----------------------------------------------
    # Paper code (M21–M23 schemes, legacy papers) states the TZ outright. Barcode-only
    # documents: within a session the barcodes for successive TZs step by 5
    # (e.g. 7106 / 7111 / 7116), so TZ = (n - base)/5 + 1 where base is the lowest
    # barcode seen for that session + paper across QPs *and* MSs.
    base = {}
    for r in uniq:
        if r["barcode"]:
            k = (r["session"], r["year"], r["paper"])
            n = int(r["barcode"][5:])
            base[k] = min(base.get(k, n), n)
    for r in uniq:
        if r.get("code"):
            r["tz"], r["tz_src"] = r["code_tz"], "paper code"
        elif r["barcode"]:
            k = (r["session"], r["year"], r["paper"])
            off = int(r["barcode"][5:]) - base[k]
            r["tz"], r["tz_src"] = (off // 5 + 1, "barcode offset") if off % 5 == 0 else (None, "?")
        else:
            r["tz"], r["tz_src"] = None, "?"

    # ---- pair QP -> MS ----------------------------------------------------------------
    pairs, used = [], set()
    for q in qps:
        cand = [m for m in mss if m["barcode"] and q["barcode"] and m["barcode"] == q["barcode"]]
        how = "barcode"
        if not cand:
            cand = [m for m in mss if not m["barcode"] and m["session"] == q["session"]
                    and m["year"] == q["year"] and m["paper"] == q["paper"] and m["subject"] == q["subject"]]
            how = "session+paper"
            if len(cand) > 1:
                # several TZs in that session: the TZ number must agree with the best
                # per-part-marks fingerprint, otherwise flag it
                by_tz = [m for m in cand if m["tz"] == q["tz"]]
                best = max(cand, key=lambda m: parts_score(q["_parts"], m["_parts"]))
                if len(by_tz) == 1 and by_tz[0] is best:
                    cand, how = by_tz, "session+TZ, parts agree"
                else:
                    report["notes"].append(f"{q['file']}: TZ says {[m['file'] for m in by_tz]}, "
                                           f"part-marks fingerprint says {best['file']}")
                    cand, how = [best], "part-marks fingerprint"
        cand = [m for m in cand if m["sha"] not in used]
        ms = None
        if len(cand) == 1:
            ms = cand[0]
            used.add(ms["sha"])
        elif len(cand) > 1:
            report["notes"].append(f"{q['file']}: ambiguous mark scheme candidates {[c['file'] for c in cand]}")
        pairs.append({"qp": q, "ms": ms, "how": how if ms else None})

    report["pair_check"] = []
    for pr in pairs:
        q, m = pr["qp"], pr["ms"]
        if not m:
            continue
        rivals = [x for x in mss if x["session"] == q["session"] and x["year"] == q["year"]
                  and x["paper"] == q["paper"] and x["subject"] == q["subject"]]
        scores = sorted(((parts_score(q["_parts"], x["_parts"]), x["file"]) for x in rivals), reverse=True)
        mine = parts_score(q["_parts"], m["_parts"])
        ok = mine >= scores[0][0] - 1e-9
        pr["check"] = (round(mine, 3), round(max([s for s, f in scores if f != m["file"]], default=0), 3), ok)
        if not ok:
            report["pair_check"].append({"qp": q["file"], "ms": m["file"], "score": mine, "better": scores[0]})

    for m in mss:
        if m["sha"] not in used:
            report["unpaired_ms"].append({"file": m["file"], "barcode": m["barcode"], "code": m["code"],
                                          "session": f"{m['session']} {m['year']}", "paper": m["paper"],
                                          "tz": m["tz"], "tz_src": m["tz_src"]})

    # ---- content duplicates among question papers (same session + paper) ----------------
    groups = defaultdict(list)
    for pr in pairs:
        q = pr["qp"]
        groups[(q["session"], q["year"], q["paper"], q["subject"])].append(pr)
    final = []
    for k, g in groups.items():
        g.sort(key=lambda pr: pr["qp"]["tz"] or 0)
        merged = [False] * len(g)
        for i in range(len(g)):
            if merged[i]:
                continue
            dups = []
            for j in range(i + 1, len(g)):
                if merged[j]:
                    continue
                s = similarity(g[i]["qp"]["_norm"], g[j]["qp"]["_norm"])
                report["notes"].append(f"compare {g[i]['qp']['barcode']} vs {g[j]['qp']['barcode']} "
                                       f"({k[1]} {k[0]} P{k[2]}): text similarity {s:.4f}")
                if s >= 0.97:
                    merged[j] = True
                    dups.append((g[j], s))
            pr = g[i]
            if dups:
                pr["dedup"] = True
                pr["also"] = [d["qp"]["file"] for d, _ in dups]
                if not pr["ms"]:                     # borrow a scheme from the duplicate if needed
                    pr["ms"] = next((d["ms"] for d, _ in dups if d["ms"]), None)
                report["content_duplicates"].append({
                    "kept": pr["qp"]["file"], "kept_barcode": pr["qp"]["barcode"],
                    "dropped": [{"file": d["qp"]["file"], "barcode": d["qp"]["barcode"], "similarity": round(s, 4),
                                 "ms_dropped": d["ms"]["file"] if d["ms"] else None} for d, s in dups]})
            final.append(pr)

    # ---- emit papers.json ------------------------------------------------------------------
    out = []
    for pr in final:
        q, m = pr["qp"], pr["ms"]
        # Drop the TZ when the paper is a merged duplicate, or when the session had only one
        # variant (counting mark schemes too, so a lone QP whose sibling TZ only survives as
        # an orphan scheme keeps its TZ). A TZ stated in the paper code is always kept.
        variants = {d["barcode"] or d["code"] for d in uniq if d["session"] == q["session"] and
                    d["year"] == q["year"] and d["paper"] == q["paper"] and d["subject"] == q["subject"]
                    and not (d["is_ms"] and d["code"] and not d["barcode"])}
        if pr.get("dedup"):
            tz = None
        elif q["tz_src"] == "paper code":
            tz = q["tz"] or None
        else:
            tz = q["tz"] if len(variants) > 1 else None
        sid = f"{q['session'][0]}{q['year'] % 100:02d}P{q['paper']}TZ{tz or 0}"
        label = f"{q['session']} {q['year']} · Paper {q['paper']}" + (f" · TZ{tz}" if tz else "")
        # MS only prints "Total [N marks]" for multi-part questions, so its list must be an
        # in-order subsequence of the QP's per-question marks
        if m:
            it = iter(q["marks"])
            if not all(any(x == y for y in it) for x in m["marks"]):
                report["mark_mismatch"].append({"id": sid, "qp_marks": q["marks"], "ms_totals": m["marks"]})
        if not m:
            report["unpaired_qp"].append({"id": sid, "label": label, "file": q["file"]})
        out.append({
            "id": sid, "label": label, "session": q["session"], "year": q["year"], "paper": q["paper"],
            "tz": tz, "tz_source": q["tz_src"] if tz else None,
            "syllabus": "current" if q["subject"] == "AA" else "legacy",
            "subject": "Mathematics: analysis and approaches HL" if q["subject"] == "AA" else "Mathematics HL (pre-2019)",
            "qp_file": q["file"], "qp_barcode": q["barcode"], "qp_code": q["code"], "qp_date": q["date_line"],
            "qp_pages": q["pages"],
            "ms_file": m["file"] if m else None, "ms_barcode": m["barcode"] if m else None,
            "ms_code": m["code"] if m else None, "ms_pages": m["pages"] if m else None,
            "paired_by": pr["how"] if m else None,
            "pair_content_score": pr.get("check", (None, None))[0], "best_rival_score": pr.get("check", (None, None))[1],
            "questions": len(q["marks"]), "marks": q["marks"], "total": sum(q["marks"]),
            "ms_totals": m["marks"] if m else None,
            "duplicate_of_this": pr.get("also", []),
        })
    out.sort(key=lambda p: (p["syllabus"] != "current", -p["year"], p["session"] != "November", p["paper"], p["tz"] or 0))

    (HERE / "papers.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    (HERE / "identify_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))

    # ---- console table ------------------------------------------------------------------
    print(f"{'id':11} {'label':30} {'Qs':>3} {'mk':>4}  {'QP':10} {'MS':16} {'paired by':22} {'match/rival':11} TZ from")
    for p in out:
        ms = (p["ms_barcode"] or p["ms_code"] or "-") if p["ms_file"] else "—— NONE ——"
        sc = f"{p['pair_content_score']:.2f}/{p['best_rival_score']:.2f}" if p["ms_file"] else ""
        print(f"{p['id']:11} {p['label']:30} {p['questions']:3} {p['total']:4}  {(p['qp_barcode'] or ''):10} "
              f"{ms[:16]:16} {(p['paired_by'] or ''):22} {sc:11} {p['tz_source'] or '-'}")
    print(f"\n{len(out)} papers, {sum(p['questions'] for p in out)} questions, {sum(p['total'] for p in out)} marks")
    for k in ("skipped_non_pdf", "unreadable", "excluded", "byte_duplicates", "content_duplicates",
              "unpaired_qp", "unpaired_ms", "mark_mismatch", "pair_check"):
        if report[k]:
            print(f"\n[{k}]")
            for x in report[k]:
                print("  ", x)
    print("\n[similarity checks]")
    for n in report["notes"]:
        print("  ", n)


if __name__ == "__main__":
    main()
