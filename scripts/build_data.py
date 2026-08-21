#!/usr/bin/env python3
"""Build data/bible.sqlite from public-domain sources.

  KJV  - King James Version (public domain)
  CUV  - Chinese Union Version / 和合本 (public domain, 1919)

The Chinese Recovery Version (恢复本) is under copyright and is NOT bundled.
Add it with:  python scripts/import_rcv.py <your-file>

Usage:  python scripts/build_data.py [--offline]
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sqlite3
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from books import ABBR_ZH, BOOKS, BY_SOURCE_NAME  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(HERE, "_cache")
DB_PATH = os.path.join(ROOT, "data", "bible.sqlite")

BASE = "https://raw.githubusercontent.com/scrollmapper/bible_databases/master/formats/csv"
SOURCES = {"KJV": f"{BASE}/KJV.csv", "ChiUn": f"{BASE}/ChiUn.csv"}

VERSIONS = [
    # code, display name, short badge, language, order, copyright note
    ("RCV", "中文恢复本圣经 · Recovery Version (Chinese)", "恢复本", "zh", 1,
     "© Living Stream Ministry — not distributed with this app; supplied locally by the user."),
    ("CUV", "中文和合本 · Chinese Union Version", "和合本", "zh", 2,
     "Public domain (1919)."),
    ("KJV", "King James Version", "KJV", "en", 3,
     "Public domain."),
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS versions (
    code TEXT PRIMARY KEY, name TEXT, short TEXT, lang TEXT,
    ord INTEGER, copyright TEXT
);
CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY, osis TEXT, name_en TEXT,
    name_zh_t TEXT, name_zh_s TEXT, abbr_zh_t TEXT, abbr_zh_s TEXT,
    testament TEXT, chapters INTEGER
);
CREATE TABLE IF NOT EXISTS verses (
    version TEXT NOT NULL, book INTEGER NOT NULL, chapter INTEGER NOT NULL,
    verse INTEGER NOT NULL, text TEXT NOT NULL, text_s TEXT,
    PRIMARY KEY (version, book, chapter, verse)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS idx_verses_ref ON verses (book, chapter, verse);
"""

CJK = r"⺀-鿿　-〿＀-￯"
_SPACE_IN_CJK = re.compile(rf"(?<=[{CJK}])[ \t]+(?=[{CJK}])")
_EDGE_SPACE = re.compile(rf"(?<=[{CJK}])[ \t]+|[ \t]+(?=[{CJK}])")


def clean_zh(text: str) -> str:
    """SWORD Chinese modules ship word-segmented with spaces; CUV has none."""
    text = re.sub(r"<[^>]*>", "", text).replace("　", "")
    while True:
        new = _SPACE_IN_CJK.sub("", text)
        if new == text:
            break
        text = new
    return _EDGE_SPACE.sub("", text).strip()


def clean_en(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def fetch(name: str, url: str, offline: bool) -> str:
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"{name}.csv")
    if not os.path.exists(path):
        if offline:
            raise SystemExit(f"missing cached source {path} and --offline was given")
        print(f"  downloading {name} …")
        urllib.request.urlretrieve(url, path)
    return path


def read_source(path: str, lang: str):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            book = BY_SOURCE_NAME.get(row["Book"].strip())
            if book is None:
                raise SystemExit(f"unknown book name in source: {row['Book']!r}")
            text = clean_zh(row["Text"]) if lang == "zh" else clean_en(row["Text"])
            # SWORD marks a verse merged into the previous one with a bare "a".
            if lang == "zh" and text == "a":
                text = ""
            yield book, int(row["Chapter"]), int(row["Verse"]), text


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="use cached CSVs only")
    args = ap.parse_args()

    try:
        from opencc import OpenCC
        t2s = OpenCC("t2s").convert
    except ImportError:
        print("! opencc not installed — 简体 will fall back to 繁體")
        print("  pip install opencc-python-reimplemented, then re-run")
        t2s = None

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    db = sqlite3.connect(DB_PATH)
    db.executescript(SCHEMA)
    db.executemany("INSERT INTO versions VALUES (?,?,?,?,?,?)", VERSIONS)
    db.executemany(
        "INSERT INTO books VALUES (?,?,?,?,?,?,?,?,0)",
        [(i, osis, en, zh, t2s(zh) if t2s else zh, ab, t2s(ab) if t2s else ab, t)
         for (i, osis, en, zh, t), ab in zip(BOOKS, ABBR_ZH)],
    )

    for code, src, lang in (("KJV", "KJV", "en"), ("CUV", "ChiUn", "zh")):
        print(f"building {code} …")
        path = fetch(src, SOURCES[src], args.offline)
        rows = list(read_source(path, lang))
        db.executemany(
            "INSERT OR REPLACE INTO verses VALUES (?,?,?,?,?,?)",
            [(code, b, c, v, t, (t2s(t) if (t2s and lang == "zh") else None))
             for b, c, v, t in rows],
        )
        print(f"  {len(rows):,} verses")

    refresh_counts(db)
    db.execute("INSERT OR REPLACE INTO meta VALUES ('source',?)",
               ("scrollmapper/bible_databases (KJV, ChiUn)",))
    db.commit()
    db.execute("VACUUM")
    db.close()
    print(f"wrote {DB_PATH} ({os.path.getsize(DB_PATH)/1e6:.1f} MB)")


def refresh_counts(db: sqlite3.Connection) -> None:
    """Chapter counts come from whichever version reaches furthest."""
    db.execute(
        "UPDATE books SET chapters = COALESCE("
        "(SELECT MAX(chapter) FROM verses WHERE verses.book = books.id), 0)"
    )


if __name__ == "__main__":
    main()
