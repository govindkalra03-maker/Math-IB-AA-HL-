"""Stage 3 — classify every question against the AA HL syllabus.

Classification itself is done by reading each question's image (the slow, expensive part);
this script organises that work and guards its output:

    classify.py prepare [n_batches]   write out/classify/batch_K.json for every question that
                                      is not yet in classify.json (papers kept together)
    classify.py merge [--overwrite]   validate out/classify/result_K.json files and fold them
                                      into classify.json  {question_id: [code, desc]}
    classify.py status                coverage and per-code counts

classify.json is the cache: anything already in it is never re-queued, so a rebuild of
later stages never repeats classification.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))            # run with -I: make sibling modules importable
from syllabus import SYLLABUS, TOPICS, sort_key, topic_of  # noqa: E402
OUT = HERE / "out"
WORK = OUT / "classify"
CACHE = HERE / "classify.json"


def qid(pid, q):
    return f"{pid}-Q{q}"


def all_questions():
    papers = {p["id"]: p for p in json.loads((HERE / "papers.json").read_text())}
    ex = json.loads((OUT / "extract.json").read_text())
    rows = []
    for pid, p in papers.items():
        for q in ex[pid]["questions"]:
            rows.append({"id": qid(pid, q["q"]), "paper": pid, "label": p["label"],
                         "syllabus": p["syllabus"], "marks": q["marks"],
                         "images": [str(OUT / "png" / f.replace(".webp", ".png")) for f in q["qi"]]})
    return rows


def load_cache():
    return json.loads(CACHE.read_text()) if CACHE.exists() else {}


def prepare(n):
    cache = load_cache()
    todo = [r for r in all_questions() if r["id"] not in cache]
    WORK.mkdir(parents=True, exist_ok=True)
    for old in WORK.glob("batch_*.json"):
        old.unlink()
    by_paper = {}
    for r in todo:
        by_paper.setdefault(r["paper"], []).append(r)
    # greedy: largest paper groups first into the lightest batch
    batches = [[] for _ in range(max(1, n))]
    for grp in sorted(by_paper.values(), key=len, reverse=True):
        min(batches, key=len).extend(grp)
    for k, b in enumerate(batches):
        if b:
            (WORK / f"batch_{k}.json").write_text(json.dumps(b, indent=1))
            print(f"batch_{k}: {len(b)} questions from {sorted({r['paper'] for r in b})}")
    print(f"{len(todo)} questions queued; {len(cache)} already classified")


VAGUE = re.compile(r"^(complex numbers|vectors|calculus|probability|statistics|functions|integration|"
                   r"differentiation|trigonometry|sequences|algebra|geometry)\.?$", re.I)


def merge(overwrite=False):
    cache = load_cache()
    known = {r["id"]: r for r in all_questions()}
    problems, added = [], 0
    for f in sorted(WORK.glob("result_*.json")):
        try:
            res = json.loads(f.read_text())
        except json.JSONDecodeError as e:
            problems.append(f"{f.name}: not valid JSON ({e})")
            continue
        for k, v in res.items():
            if k not in known:
                problems.append(f"{f.name}: unknown question id {k}")
                continue
            if not (isinstance(v, list) and len(v) == 2 and all(isinstance(x, str) for x in v)):
                problems.append(f"{f.name}: {k} is not [code, desc]: {v!r}")
                continue
            code, desc = v[0].strip(), v[1].strip()
            if code not in SYLLABUS:
                problems.append(f"{f.name}: {k} has unknown code {code!r}")
                continue
            if len(desc) < 15 or VAGUE.match(desc):
                problems.append(f"{f.name}: {k} description too vague: {desc!r}")
                continue
            if code.startswith("LEGACY") and known[k]["syllabus"] == "current":
                problems.append(f"{f.name}: {k} is a current-syllabus question coded {code}")
                continue
            if k in cache and not overwrite:
                continue
            cache[k] = [code, desc]
            added += 1
    ordered = {k: cache[k] for k in sorted(cache, key=lambda k: (sort_key(cache[k][0]), k))}
    CACHE.write_text(json.dumps(ordered, indent=1, ensure_ascii=False))
    missing = [k for k in known if k not in cache]
    print(f"merged {added} new; classify.json now has {len(cache)}/{len(known)}; missing {len(missing)}")
    for p in problems:
        print("  !!", p)
    if missing:
        print("  missing:", missing[:40], "…" if len(missing) > 40 else "")
    return problems, missing


def status():
    cache = load_cache()
    known = {r["id"]: r for r in all_questions()}
    by_topic = Counter(topic_of(c) for c, _ in cache.values())
    marks = Counter()
    for k, (c, _) in cache.items():
        marks[topic_of(c)] += known[k]["marks"]
    print(f"{len(cache)}/{len(known)} classified")
    for t, name in TOPICS.items():
        print(f"  Topic {t} {name:28} {by_topic[t]:4} questions {marks[t]:5} marks")
    codes = Counter(c for c, _ in cache.values())
    unused = [c for c in SYLLABUS if c not in codes]
    print("per code:", ", ".join(f"{c}:{n}" for c, n in sorted(codes.items(), key=lambda x: sort_key(x[0]))))
    print("codes with no questions:", unused)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "prepare":
        prepare(int(sys.argv[2]) if len(sys.argv) > 2 else 6)
    elif cmd == "merge":
        merge("--overwrite" in sys.argv)
    else:
        status()
