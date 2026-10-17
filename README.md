# IB Maths HL Paper Lab

An offline study pipeline for **IB Mathematics: Analysis & Approaches HL**. Point it at a folder of
past-paper PDFs and mark schemes, and it builds:

- **Five topic PDFs**: every question grouped by syllabus sub-topic, each followed by its mark scheme,
  with a clickable contents page and sidebar bookmarks.
- **HL Paper Lab**: a single-file HTML question bank. You can filter, search and sort questions, open
  each one with its mark scheme, and generate mock exams that hit a target mark total and print as an
  IB-style paper.

> **No IB material is included in this repository.** Past papers and mark schemes are
> © International Baccalaureate Organization. You need your own copies. Everything the pipeline
> generates from them (`out/`, `dist/`, `verify/`) is git-ignored and meant for personal study only.

## How it works

Each stage is its own script and caches its output, so you can re-run one without redoing the others.

| Stage | Script | What it does |
|---|---|---|
| 1 | `identify.py` | Identifies every PDF from its cover, not its filename: barcode or paper code, session, paper number, level, language. Excludes Further Maths, SL, non-English and Paper 3. Pairs each paper with its mark scheme (checked by matching per-part marks) and merges duplicate papers. Writes `papers.json`. |
| 2 | `extract.py` | Crops each question as an image (200 dpi), starting at its `[Maximum mark: N]` line. Strips ruled answer boxes and page furniture, and stitches questions that run across pages. Finds mark-scheme sections from the left-margin question numbers. Writes greyscale PNGs and 8-level lossless WebPs to `out/`. |
| 3 | `classify.py` | Prepares batches of question images and merges the classification results into `classify.json` (`{id: [code, description]}`), checked against the syllabus in `syllabus.py`. The classifying itself is done by reading each image. |
| 4 | `build_db.py` | Combines everything into `out/db.json`, one record per question. |
| 5 | `author_ms.py`, `verify_ms.py` | For papers with no mark scheme: IB-style worked mark schemes. Every result is checked with sympy, and code asserts that the marks per part and per question match the paper. Rendered with an amber **UNOFFICIAL** banner so they can never be mistaken for IB schemes. |
| 6 | `build_pdfs.py` | Builds the five topic PDFs with ReportLab, then reads them back to check that every link and bookmark lands on its intended page (`--verify`). |
| 7 | `build_app.py` | Builds `dist/HL Paper Lab.html` (self-contained, images as `data:` URIs) and `dist/local/` (separate PNGs). Its source is in `app/` (vanilla JS, no build step). |
| 8 | `verify.py` | Independent end-to-end checks: data integrity, PDF coverage and links, authored-scheme marks, and the dashboard driven with Playwright (search, filters, reader, exam generator, print output). |

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m playwright install chromium   # only needed for verify.py
```

## Run

```bash
export IB_PAPERS_DIR="/path/to/your/past papers"   # defaults to ~/Downloads/School/Math/Past Papers
.venv/bin/python -I identify.py
.venv/bin/python -I extract.py
.venv/bin/python -I classify.py prepare      # then classify the batches in out/classify/
.venv/bin/python -I classify.py merge
.venv/bin/python -I author_ms.py             # only if a paper has no mark scheme
.venv/bin/python -I build_db.py
.venv/bin/python -I build_pdfs.py
.venv/bin/python -I build_app.py
.venv/bin/python -I verify.py
```

Then open `dist/HL Paper Lab.html` in any browser. It works offline.

`author_ms.py` contains worked schemes for one specific paper (May 2017 Paper 1 TZ2, pre-2019
Mathematics HL), written because that paper's scheme was missing. They are unofficial worked solutions,
not IB documents.
