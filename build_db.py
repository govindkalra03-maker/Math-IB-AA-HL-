"""Stage 4 — join papers.json, out/extract.json and classify.json into out/db.json.

One record per question, sorted by topic, then syllabus code, then newest first.
Mark schemes authored in Stage 5 (out/authored.json, if present) fill empty `mi` lists and
set msAuthored: true — official schemes are never replaced.

    .venv/bin/python -I build_db.py
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from syllabus import SYLLABUS, TOPICS, level_of, sort_key, topic_of  # noqa: E402

OUT = HERE / "out"
SESSION_ORDER = {"May": 0, "November": 1}          # November is later in the same year
SUBSCRIPT = dict(zip("0123456789aehiklmnoprstuvx", "₀₁₂₃₄₅₆₇₈₉ₐₑₕᵢₖₗₘₙₒₚᵣₛₜᵤᵥₓ"))


def tidy(desc):
    """Normalise ASCII subscripts like S_n / u_k to Unicode (S_N has no Unicode form: left as is)."""
    return re.sub(r"(?<=[A-Za-z0-9)])_([0-9a-z])(?![A-Za-z0-9])",
                  lambda m: SUBSCRIPT.get(m.group(1), m.group(0)), desc)


def main():
    papers = {p["id"]: p for p in json.loads((HERE / "papers.json").read_text())}
    extract = json.loads((OUT / "extract.json").read_text())
    classes = json.loads((HERE / "classify.json").read_text())
    authored_path = OUT / "authored.json"
    authored = json.loads(authored_path.read_text()) if authored_path.exists() else {}

    db, problems = [], []
    for pid, p in papers.items():
        for q in extract[pid]["questions"]:
            qid = f"{pid}-Q{q['q']}"
            if qid not in classes:
                problems.append(f"{qid}: not classified")
                continue
            code, desc = classes[qid]
            mi, ms_authored = q["mi"], False
            if not mi and qid in authored:
                mi, ms_authored = authored[qid]["mi"], True
            db.append({
                "id": qid,
                "topic": topic_of(code), "topicName": TOPICS[topic_of(code)],
                "code": code, "sub": SYLLABUS[code],
                "desc": tidy(desc),
                "level": level_of(code),
                "paper": p["paper"], "session": p["session"], "year": p["year"], "tz": p["tz"],
                "label": p["label"], "q": q["q"], "marks": q["marks"],
                "calc": p["paper"] != 1,
                "current": p["syllabus"] == "current",
                "section": "A" if q["marks"] <= 12 else "B",
                "qi": q["qi"], "mi": mi,
                "msAuthored": ms_authored,
            })

    db.sort(key=lambda r: (r["topic"], sort_key(r["code"]), -r["year"], -SESSION_ORDER[r["session"]],
                           r["paper"], r["tz"] or 0, r["q"]))

    # ---- checks --------------------------------------------------------------------------
    ids = [r["id"] for r in db]
    assert len(ids) == len(set(ids)), "duplicate question ids"
    assert len(db) == sum(len(extract[pid]["questions"]) for pid in papers), "question count mismatch"
    for r in db:
        for f in r["qi"] + r["mi"]:
            if not (OUT / "img" / f).exists():
                problems.append(f"{r['id']}: missing image {f}")
        if not r["qi"]:
            problems.append(f"{r['id']}: no question image")
    for pid, p in papers.items():
        got = sum(r["marks"] for r in db if r["id"].startswith(pid + "-"))
        if got != p["total"]:
            problems.append(f"{pid}: marks {got} != paper total {p['total']}")

    (OUT / "db.json").write_text(json.dumps(db, indent=1, ensure_ascii=False))

    no_ms = [r["id"] for r in db if not r["mi"]]
    print(f"out/db.json: {len(db)} questions, {sum(r['marks'] for r in db)} marks")
    t = Counter(r["topic"] for r in db)
    for k, name in TOPICS.items():
        print(f"  Topic {k} {name:28} {t[k]:4} questions  {sum(r['marks'] for r in db if r['topic'] == k):5} marks")
    print("  level:", dict(Counter(r["level"] for r in db)),
          " section:", dict(Counter(r["section"] for r in db)),
          " calc:", dict(Counter(r["calc"] for r in db)),
          " current:", dict(Counter(r["current"] for r in db)))
    print(f"  official MS: {sum(1 for r in db if r['mi'] and not r['msAuthored'])}, "
          f"authored MS: {sum(r['msAuthored'] for r in db)}, no MS yet: {len(no_ms)} {no_ms}")
    for pr in problems:
        print("  !!", pr)
    print("OK" if not problems else f"{len(problems)} problems")


if __name__ == "__main__":
    main()
