"""Stage 7 — build the HL Paper Lab dashboard.

    dist/HL Paper Lab.html     one self-contained file: inline CSS + JS, data as JSON, every image as a
                               base64 data: URI (the 8-level WebP crops). Opens by double-clicking.
    dist/local/index.html      the same app reading full-resolution PNGs from dist/local/img/.

Sources live in app/ (template.html, app.css, app.js); no build step beyond this script.

    .venv/bin/python -I build_app.py
"""
import base64
import json
import shutil
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from syllabus import SYLLABUS, TOPICS, sort_key  # noqa: E402

OUT, DIST, APP = HERE / "out", HERE / "dist", HERE / "app"


def script_json(obj):
    """JSON safe to embed inside <script>: no '</' sequences, no stray line separators."""
    s = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return s.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def page(data, images, mode):
    html = (APP / "template.html").read_text()
    parts = {"{{CSS}}": (APP / "app.css").read_text(), "{{JS}}": (APP / "app.js").read_text(),
             "{{DATA}}": script_json(data), "{{IMGS}}": script_json(images), "{{MODE}}": mode}
    for k, v in parts.items():
        assert html.count(k) == 1, f"template placeholder {k} must appear exactly once"
        html = html.replace(k, v)
    return html


def main():
    db = json.loads((OUT / "db.json").read_text())
    papers = json.loads((HERE / "papers.json").read_text())
    keep = ["id", "topic", "topicName", "code", "sub", "desc", "level", "paper", "session", "year", "tz",
            "label", "q", "marks", "calc", "current", "section", "qi", "mi", "msAuthored"]
    data = {
        "db": [{k: r[k] for k in keep} for r in db],
        "meta": {"topics": {str(k): v for k, v in TOPICS.items()},
                 "syllabus": SYLLABUS,
                 "order": sorted(SYLLABUS, key=sort_key),
                 "papers": len(papers),
                 "built": date.today().isoformat()},
    }
    files = sorted({f for r in db for f in r["qi"] + r["mi"]})
    missing = [f for f in files if not (OUT / "img" / f).exists() or not (OUT / "png" / f.replace(".webp", ".png")).exists()]
    assert not missing, f"missing images: {missing[:10]}"

    # 1) single self-contained file
    images = {f: "data:image/webp;base64," + base64.b64encode((OUT / "img" / f).read_bytes()).decode()
              for f in files}
    DIST.mkdir(exist_ok=True)
    single = DIST / "HL Paper Lab.html"
    single.write_text(page(data, images, "inline"), encoding="utf-8")

    # 2) local copy with separate full-resolution PNGs
    local = DIST / "local"
    img_dir = local / "img"
    if img_dir.exists():
        shutil.rmtree(img_dir)
    img_dir.mkdir(parents=True)
    for f in files:
        png = f.replace(".webp", ".png")
        shutil.copy2(OUT / "png" / png, img_dir / png)
    (local / "index.html").write_text(page(data, {}, "files"), encoding="utf-8")

    size_local = sum(p.stat().st_size for p in local.rglob("*") if p.is_file())
    print(f"{single.relative_to(HERE)}: {single.stat().st_size / 1e6:.1f} MB "
          f"({len(db)} questions, {len(files)} images inline)")
    print(f"{(local / 'index.html').relative_to(HERE)}: {(local / 'index.html').stat().st_size / 1e3:.0f} KB "
          f"+ {len(files)} PNGs ({size_local / 1e6:.1f} MB total)")


if __name__ == "__main__":
    main()
