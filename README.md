# 三版本圣经对照 · Three-Version Bible Comparison

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io/deploy?repository=mzhao577/bible-3-versions&branch=main&mainModule=app.py)

A Streamlit app that reads the Bible **verse by verse across three versions at once**:

| 版本 | Version | 状态 |
| --- | --- | --- |
| 恢复本 | 中文恢复本圣经 · Chinese Recovery Version | 自行上传（版权所限，见下） |
| 和合本 | 中文和合本 · Chinese Union Version (1919) | 已收录（公有领域） |
| KJV | King James Version | 已收录（公有领域） |

Features: book → chapter → verse navigation, prev/next chapter paging, a search box
(Chinese simplified **or** traditional, English case-insensitive, multi-word AND),
reference shortcuts (`约3:16`, `John 3:16`, `林前13:4`), stacked or side-by-side
layout, 简体/繁體 toggle, font size and serif controls, and shareable deep links
(`?b=43&c=3&v=16`).

## Quick start

```bash
pip install -r requirements.txt
streamlit run app.py
```

`data/bible.sqlite` is committed, so there is nothing to build at boot. To
regenerate it from source instead:

```bash
pip install -r requirements-build.txt
python scripts/build_data.py        # downloads KJV + CUV, writes data/bible.sqlite
```

## Adding the Recovery Version

The Chinese Recovery Version is **© Living Stream Ministry**. It is not public
domain and is therefore not bundled here — redistributing it would infringe that
copyright. Load your own licensed copy one of two ways.

### In the app (works on the deployed site)

Sidebar → **载入恢复本 Load Recovery Version** → upload your file.

The text is held in `st.session_state`, which means it is scoped to **your**
browser session: never written to `data/bible.sqlite`, never served to anyone
else who opens the public URL, and gone when the session ends. Re-upload each
time you want it.

### On your own machine (persists)

```bash
python scripts/import_rcv.py path/to/your/recovery.csv --strip-notes
```

This writes into `data/bible.sqlite`. Keep that modified database out of any
repo you publish — the deployed app would republish the text to every visitor.

### Accepted formats

Both paths auto-detect the same shapes:

| Format | Shape |
| --- | --- |
| `.csv` / `.tsv` | header row with book / chapter / verse / text columns (English or 中文 headers, any order) |
| `.json` | `[{"book":…,"chapter":…,"verse":…,"text":…}]`, `{"Gen":{"1":{"1":"…"}}}`, or `[{"name":…,"chapters":[["v1",…],…]}]` |
| `.bbl.mybible`, `.bblx`, any SQLite | a table with `Book` / `Chapter` / `Verse` / `Scripture` columns (MySword, e-Sword) |
| `.txt` | one verse per line: `创 1:1 起初，神创造天地。` |

Book names may be OSIS (`1Cor`), English (`I Corinthians`), full Chinese
(`哥林多前书`, 简 or 繁), or the standard abbreviation (`林前`). Chapter/verse must
be numeric. **去除注解标记 / `--strip-notes`** drops footnote markers such as
`<RF>…<Rf>`, `[1]` and `（注…）`.

A partial import is fine — the app shows `（此版本无此节）` wherever a version has
no text, and search covers whatever was loaded.

Use `--version CODE` (CLI) to load some other translation into an extra slot.

## Deploying to Streamlit Community Cloud

Click the badge above — it opens Streamlit's deploy form with this repo, `main`
and `app.py` already filled in. Sign in with GitHub and press **Deploy**.

Manually: <https://share.streamlit.io> → **New app** → pick the repo/branch →
main file `app.py`.

Only the two public-domain versions ship in `data/bible.sqlite`, so the deployed
app republishes nothing under copyright. Visitors who hold the Recovery Version
can load their own copy through the sidebar; it stays private to their session.

## Layout

```
app.py                   the Streamlit app
data/bible.sqlite        versions, books, verses (traditional + simplified columns)
scripts/books.py         canonical 66-book table, names and abbreviations
scripts/build_data.py    builds the database from public-domain sources
scripts/import_rcv.py    parses a locally-held Recovery Version (CLI + the app's uploader)
requirements.txt         runtime dependencies (streamlit, opencc)
requirements-build.txt   build-only dependency (opencc, for 简体 conversion)
```

## Sources and licensing

- KJV and CUV verse text: [scrollmapper/bible_databases](https://github.com/scrollmapper/bible_databases)
  (both translations are public domain). The CUV module ships word-segmented;
  `build_data.py` strips the segmentation spaces and generates a simplified
  column with [OpenCC](https://github.com/BYVoid/OpenCC).
- Verse alignment follows KJV versification; the CUV carries two extra verses
  (3 John 1:15, Revelation 12:18) and 70 verses merged into the preceding one,
  shown as （与上节合并）.
- The Recovery Version text is © Living Stream Ministry and is not included.
