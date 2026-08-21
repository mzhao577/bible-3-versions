#!/usr/bin/env python3
"""Load a locally-held Chinese Recovery Version text into data/bible.sqlite.

The Recovery Version (中文恢复本圣经) is © Living Stream Ministry, so its text
is not distributed with this project. Point this script at your own copy:

    python scripts/import_rcv.py path/to/recovery.csv
    python scripts/import_rcv.py path/to/recovery.json
    python scripts/import_rcv.py path/to/module.bbl.mybible   # MySword
    python scripts/import_rcv.py path/to/module.bblx          # e-Sword
    python scripts/import_rcv.py path/to/plain.txt

Accepted shapes
    csv/tsv   header row containing book / chapter / verse / text columns,
              in any order and under common aliases (Book, 书卷, b, c, v …).
    json      [{"book":…, "chapter":…, "verse":…, "text":…}, …]
              or  {"Gen": {"1": {"1": "…"}}}
              or  [{"name":…, "chapters": [["v1", "v2", …], …]}, …]
    sqlite    a table with Book / Chapter / Verse / Scripture columns
              (MySword .bbl.mybible and e-Sword .bblx both match).
    txt       one verse per line:  创 1:1 起初，神创造天地。

Use --version CODE to load some other translation into another slot.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from books import lookup_table  # noqa: E402
from build_data import DB_PATH, clean_zh, refresh_counts  # noqa: E402

COL_ALIASES = {
    "book": {"book", "book_name", "bookname", "b", "书", "书卷", "書", "書卷", "卷"},
    "chapter": {"chapter", "chap", "c", "章"},
    "verse": {"verse", "vers", "v", "节", "節"},
    "text": {"text", "scripture", "verse_text", "content", "t", "经文", "經文", "内容"},
}
# One verse per line:  创 1:1  起初…   |   1 John 3:16 …
# Some editions split a long verse across two lines (创 1:2上 / 创 1:2下) or
# label a line with several verse numbers (创 1:6,6); both are keyed to the
# first number, and parse_file() joins the parts back into one verse.
LINE_RE = re.compile(r"^\s*(?P<book>\d?\s*[A-Za-z][A-Za-z .]*|[^\d\s:：.]+)"
                     r"\s*(?P<chapter>\d+)\s*[:：.]\s*(?P<verse>\d+)"
                     r"(?P<part>[上中下]?)(?:\s*[,，]\s*\d+)*"
                     r"\s*(?P<text>.+?)\s*$")


def resolve_books():
    try:
        from opencc import OpenCC
        return lookup_table(OpenCC("t2s").convert), OpenCC("t2s").convert
    except ImportError:
        return lookup_table(), None


def norm_col(name: str) -> str | None:
    key = re.sub(r"[\s_]+", "", str(name or "")).strip().lower()
    for canon, aliases in COL_ALIASES.items():
        if key in aliases:
            return canon
    return None


# ---------------------------------------------------------------- readers

def read_delimited(path: str):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        sample = fh.read(8192)
        fh.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
        except csv.Error:
            dialect = csv.excel
        reader = csv.reader(fh, dialect)
        header = next(reader)
        cols = [norm_col(h) for h in header]
        if not {"book", "chapter", "verse", "text"} <= set(c for c in cols if c):
            raise ValueError(
                f"could not find book/chapter/verse/text columns in header: {header}"
            )
        idx = {c: i for i, c in enumerate(cols) if c}
        for row in reader:
            if len(row) <= max(idx.values()):
                continue
            yield (row[idx["book"]], row[idx["chapter"]],
                   row[idx["verse"]], row[idx["text"]])


def read_json(path: str):
    with open(path, encoding="utf-8-sig") as fh:
        data = json.load(fh)

    if isinstance(data, dict):                      # {"Gen": {"1": {"1": "…"}}}
        for book, chapters in data.items():
            for chapter, verses in chapters.items():
                for verse, text in verses.items():
                    yield book, chapter, verse, text
        return

    if data and isinstance(data[0], dict) and "chapters" in data[0]:
        for entry in data:                          # [{name, chapters:[[…]]}]
            book = entry.get("name") or entry.get("abbrev") or entry.get("book")
            for ci, chapter in enumerate(entry["chapters"], 1):
                for vi, text in enumerate(chapter, 1):
                    yield book, ci, vi, text
        return

    for entry in data:                              # [{book, chapter, verse, text}]
        rec = {norm_col(k): v for k, v in entry.items() if norm_col(k)}
        yield rec.get("book"), rec.get("chapter"), rec.get("verse"), rec.get("text")


def read_sqlite(path: str):
    src = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    tables = [r[0] for r in src.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','view')")]
    for table in tables:
        cols = [r[1] for r in src.execute(f'PRAGMA table_info("{table}")')]
        mapped = {norm_col(c): c for c in cols if norm_col(c)}
        if {"book", "chapter", "verse", "text"} <= set(mapped):
            q = (f'SELECT "{mapped["book"]}", "{mapped["chapter"]}", '
                 f'"{mapped["verse"]}", "{mapped["text"]}" FROM "{table}"')
            print(f"  reading table {table}")
            yield from src.execute(q)
            src.close()
            return
    src.close()
    raise ValueError(f"no Book/Chapter/Verse/Scripture table found in {path}")


def read_lines(path: str):
    with open(path, encoding="utf-8-sig") as fh:
        for line in fh:
            if not line.strip():
                continue
            m = LINE_RE.match(line)
            if m:
                yield m["book"], m["chapter"], m["verse"], m["text"]


def pick_reader(path: str):
    with open(path, "rb") as fh:
        if fh.read(16).startswith(b"SQLite format 3"):
            return read_sqlite
    ext = os.path.splitext(path)[1].lower()
    if ext == ".json":
        return read_json
    if ext in (".csv", ".tsv"):
        return read_delimited
    with open(path, encoding="utf-8-sig") as fh:
        head = fh.readline()
    return read_delimited if any(norm_col(c) for c in re.split(r"[,\t;|]", head)) else read_lines


NOTE_RE = re.compile(r"<[Rr][Ff]>.*?<[Rr][Ff]>|\[\d+\]|（注[^）]*）")


# ----------------------------------------------------------------- parsing

def parse_file(path: str, *, strip_notes: bool = False, quiet: bool = False):
    """Read any supported file -> (rows, unknown_book_names, skipped_count).

    Rows are (book_id, chapter, verse, text, text_simplified|None), ready for
    both the sqlite importer and the app's in-memory session store.
    """
    lookup, t2s = resolve_books()
    reader = pick_reader(path)
    if not quiet:
        print(f"reading {path} with {reader.__name__} …")

    unknown, skipped = set(), 0
    seen: dict[tuple[int, int, int], int] = {}
    merged: list[str] = []
    order: list[tuple[int, int, int]] = []
    for book, chapter, verse, text in reader(path):
        key = str(book).strip().lower().replace(" ", "").replace(".", "")
        bid = lookup.get(key) or lookup.get(re.sub(r"[書书]$", "", key))
        if bid is None:
            unknown.add(str(book))
            continue
        try:
            c, v = int(str(chapter).strip()), int(str(verse).strip())
        except (TypeError, ValueError):
            skipped += 1
            continue
        text = str(text or "")
        if strip_notes:
            text = NOTE_RE.sub("", text)
        text = clean_zh(text)
        if not text:
            continue
        if (bid, c, v) in seen:
            # a verse split across lines (…2上 / …2下) — keep both halves
            merged[seen[(bid, c, v)]] += text
        else:
            seen[(bid, c, v)] = len(merged)
            merged.append(text)
            order.append((bid, c, v))

    rows = [(b, c, v, text, t2s(text) if t2s else None)
            for (b, c, v), text in zip(order, merged)]
    return rows, unknown, skipped


def parse_bytes(filename: str, data: bytes, *, strip_notes: bool = False):
    """parse_file() for an uploaded file held in memory.

    The readers all work off paths (sqlite modules cannot be opened any other
    way), so the bytes go to a temp file that is removed before returning.
    """
    suffix = os.path.splitext(filename or "")[1] or ".txt"
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        return parse_file(path, strip_notes=strip_notes, quiet=True)
    finally:
        os.unlink(path)


# ---------------------------------------------------------------- import

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="file holding your copy of the text")
    ap.add_argument("--version", default="RCV", help="version code to fill (default RCV)")
    ap.add_argument("--db", default=DB_PATH)
    ap.add_argument("--strip-notes", action="store_true",
                    help="drop footnote/cross-reference markers like <RF>…<Rf>, [1], （注）")
    args = ap.parse_args()

    if not os.path.exists(args.db):
        raise SystemExit(f"{args.db} not found — run scripts/build_data.py first")

    try:
        parsed, unknown, skipped = parse_file(args.source, strip_notes=args.strip_notes)
    except (ValueError, OSError) as exc:
        raise SystemExit(str(exc))
    rows = [(args.version, *row) for row in parsed]

    if unknown:
        print(f"  ! unrecognised book names ignored: {sorted(unknown)[:12]}")
    if skipped:
        print(f"  ! {skipped} rows had non-numeric chapter/verse and were skipped")
    if not rows:
        raise SystemExit("nothing imported — check the file format")

    db = sqlite3.connect(args.db)
    known = db.execute("SELECT 1 FROM versions WHERE code = ?", (args.version,)).fetchone()
    if not known:
        db.execute("INSERT INTO versions VALUES (?,?,?,?,?,?)",
                   (args.version, args.version, args.version, "zh", 9,
                    "Supplied locally by the user."))
    db.execute("DELETE FROM verses WHERE version = ?", (args.version,))
    db.executemany("INSERT OR REPLACE INTO verses VALUES (?,?,?,?,?,?)", rows)
    refresh_counts(db)
    db.commit()
    books_seen = len({r[1] for r in rows})
    print(f"imported {len(rows):,} verses across {books_seen} books into '{args.version}'")
    if books_seen < 66:
        print("  (partial import — the app will show the books it has)")
    db.close()


if __name__ == "__main__":
    main()
