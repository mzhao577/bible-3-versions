"""三版本圣经对照 · Three-Version Bible Comparison.

Reads verse-by-verse across the Chinese Recovery Version (恢复本), the Chinese
Union Version (和合本) and the King James Version, with book/chapter/verse
navigation and full-text search.
"""
from __future__ import annotations

import html
import os
import re
import sqlite3
import sys
from typing import Iterable

import streamlit as st
import streamlit.components.v1 as components

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "data", "bible.sqlite")
sys.path.insert(0, os.path.join(HERE, "scripts"))

ACCENTS = {"RCV": "#d97706", "CUV": "#3b82f6", "KJV": "#10b981"}
MAX_RESULTS = 200
UPLOAD_TYPES = ["csv", "tsv", "json", "txt", "sqlite", "db", "bblx", "mybible"]

st.set_page_config(page_title="三版本圣经对照 · Bible Comparison",
                   page_icon="📖", layout="wide",
                   initial_sidebar_state="expanded")


# ----------------------------------------------------------------- data

@st.cache_resource(show_spinner=False)
def get_db() -> sqlite3.Connection:
    if not os.path.exists(DB_PATH):
        st.error("找不到 data/bible.sqlite — 请先运行 `python scripts/build_data.py`。")
        st.stop()
    return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, check_same_thread=False)


@st.cache_data(show_spinner=False)
def load_versions() -> list[dict]:
    db = get_db()
    have = {r[0] for r in db.execute("SELECT DISTINCT version FROM verses")}
    rows = db.execute(
        "SELECT code, name, short, lang, copyright FROM versions ORDER BY ord").fetchall()
    return [{"code": c, "name": n, "short": s, "lang": lg,
             "copyright": cp, "in_db": c in have}
            for c, n, s, lg, cp in rows]


def versions_now() -> list[dict]:
    """load_versions() plus whatever this session has uploaded."""
    store = local_store()
    return [{**v, "available": v["in_db"] or v["code"] in store} for v in load_versions()]


@st.cache_data(show_spinner=False)
def load_books() -> list[dict]:
    db = get_db()
    rows = db.execute(
        "SELECT id, osis, name_en, name_zh_t, name_zh_s, abbr_zh_t, abbr_zh_s, "
        "testament, chapters FROM books WHERE chapters > 0 ORDER BY id").fetchall()
    return [{"id": i, "osis": o, "en": en, "zh_t": zt, "zh_s": zs,
             "abbr_t": at, "abbr_s": asimp, "testament": t, "chapters": ch}
            for i, o, en, zt, zs, at, asimp, t, ch in rows]


@st.cache_data(show_spinner=False)
def chapter_count(book: int) -> int:
    return next(b["chapters"] for b in load_books() if b["id"] == book)


@st.cache_data(show_spinner=False)
def load_chapter(book: int, chapter: int) -> tuple[list[int], dict]:
    """-> (ordered verse numbers, {(verse, version): text_row})."""
    rows = get_db().execute(
        "SELECT verse, version, text, text_s FROM verses "
        "WHERE book = ? AND chapter = ? ORDER BY verse",
        (book, chapter)).fetchall()
    verses = sorted({r[0] for r in rows})
    return verses, {(v, code): (t, ts) for v, code, t, ts in rows}


@st.cache_data(show_spinner=False)
def load_refs(refs: tuple[tuple[int, int, int], ...]) -> dict:
    if not refs:
        return {}
    clauses = " OR ".join(["(book=? AND chapter=? AND verse=?)"] * len(refs))
    params = [x for ref in refs for x in ref]
    rows = get_db().execute(
        f"SELECT book, chapter, verse, version, text, text_s FROM verses "
        f"WHERE {clauses}", params).fetchall()
    return {(b, c, v, code): (t, ts) for b, c, v, code, t, ts in rows}


@st.cache_data(show_spinner=False)
def search_verses(query: str, codes: tuple[str, ...], testament: str,
                  book_filter: int | None, limit: int) -> list[tuple[int, int, int]]:
    """Distinct references whose text matches every whitespace-separated term."""
    terms = [t for t in query.split() if t]
    if not terms or not codes:
        return []
    where = [f"version IN ({','.join('?' * len(codes))})"]
    params: list = list(codes)
    for term in terms:
        where.append("(text LIKE ? ESCAPE '\\' OR IFNULL(text_s,'') LIKE ? ESCAPE '\\')")
        like = f"%{term.replace(chr(92), chr(92)*2).replace('%', chr(92)+'%').replace('_', chr(92)+'_')}%"
        params += [like, like]
    if book_filter:
        where.append("book = ?")
        params.append(book_filter)
    elif testament in ("OT", "NT"):
        where.append("book <= 39" if testament == "OT" else "book >= 40")
    params.append(limit)
    sql = (f"SELECT DISTINCT book, chapter, verse FROM verses WHERE {' AND '.join(where)} "
           f"ORDER BY book, chapter, verse LIMIT ?")
    return get_db().execute(sql, params).fetchall()


# -------------------------------------------- session-local (uploaded) text

def local_store() -> dict:
    """Uploaded verse text, scoped to one browser session and never written out.

    The Recovery Version is © Living Stream Ministry. Writing a user's copy
    into data/bible.sqlite would republish it to every visitor of a deployed
    app, so it lives in st.session_state instead: private to the person who
    uploaded it, gone when their session ends.
    """
    return st.session_state.setdefault("local", {})


def local_chapter(code: str, book: int, chapter: int) -> dict:
    """-> {verse: (text, text_s)} for one chapter of an uploaded version."""
    entry = local_store().get(code)
    return entry["index"].get((book, chapter), {}) if entry else {}


def local_ref(code: str, book: int, chapter: int, verse: int):
    return local_chapter(code, book, chapter).get(verse)


def local_search(code: str, terms: list[str], testament: str,
                 book_filter: int | None) -> list[tuple[int, int, int]]:
    """search_verses() over an uploaded version — same AND-of-terms semantics."""
    entry = local_store().get(code)
    if not entry or not terms:
        return []
    needles = [t.lower() for t in terms]
    hits = []
    for book, chapter, verse, text, text_s in entry["rows"]:
        if book_filter:
            if book != book_filter:
                continue
        elif (testament == "OT" and book > 39) or (testament == "NT" and book < 40):
            continue
        hay = f"{text}\n{text_s or ''}".lower()
        if all(n in hay for n in needles):
            hits.append((book, chapter, verse))
    return hits


def ingest_upload(code: str, name: str, data: bytes, strip_notes: bool) -> dict:
    """Parse an uploaded file into the session store; -> summary for the UI."""
    from import_rcv import parse_bytes

    rows, unknown, skipped = parse_bytes(name, data, strip_notes=strip_notes)
    if not rows:
        raise ValueError("文件里没有可识别的经文 — 请检查格式。")
    index: dict[tuple[int, int], dict[int, tuple[str, str | None]]] = {}
    for book, chapter, verse, text, text_s in rows:
        index.setdefault((book, chapter), {})[verse] = (text, text_s)
    local_store()[code] = {"rows": rows, "index": index, "name": name}
    return {"verses": len(rows), "books": len({r[0] for r in rows}),
            "unknown": sorted(unknown)[:8], "skipped": skipped}


# ------------------------------------------------------------ formatting

def book_label(book: dict, script: str, lang: str) -> str:
    zh = book["zh_s"] if script == "简体" else book["zh_t"]
    return f"{zh} · {book['en']}" if lang == "双语" else (zh if lang == "中文" else book["en"])


def verse_text(row: tuple[str, str | None] | None, lang: str, script: str) -> str | None:
    if row is None:
        return None
    text, text_s = row
    if lang == "zh" and script == "简体" and text_s:
        text = text_s
    return text


def highlight(text: str, terms: Iterable[str]) -> str:
    escaped = html.escape(text)
    for term in sorted({t for t in terms if t}, key=len, reverse=True):
        escaped = re.sub(f"({re.escape(html.escape(term))})",
                         r"<mark>\1</mark>", escaped, flags=re.IGNORECASE)
    return escaped


def render_verse_block(verse_no: int, texts: list[tuple[dict, str | None]],
                       *, anchor: bool, side_by_side: bool,
                       terms: Iterable[str] = ()) -> str:
    lines = []
    for meta, text in texts:
        code = meta["code"]
        if text is None:
            body = '<span class="missing">（此版本无此节）</span>'
        elif text == "":
            body = '<span class="missing">（与上节合并）</span>'
        else:
            body = highlight(text, terms) if terms else html.escape(text)
        lines.append(
            f'<div class="line {code.lower()}">'
            f'<span class="tag">{html.escape(meta["short"])}</span>'
            f'<span class="t {"zh" if meta["lang"] == "zh" else "en"}">{body}</span>'
            f"</div>")
    classes = "v" + (" cols" if side_by_side else "") + (" target" if anchor else "")
    return (f'<div class="{classes}" id="v{verse_no}">'
            f'<div class="vn">{verse_no}</div>'
            f'<div class="vbody">{"".join(lines)}</div></div>')


CSS = """
<style>
.bible { --fs: %(fs)spx; }
.bible .v { display: grid; grid-template-columns: 2.6rem 1fr; gap: .5rem;
    padding: .55rem .25rem .55rem 0; border-top: 1px solid rgba(128,128,128,.22); }
.bible .v:first-child { border-top: none; }
.bible .v.target { background: rgba(250,204,21,.14); border-radius: .5rem;
    box-shadow: inset 3px 0 0 #facc15; }
.bible .vn { font-size: .8rem; font-weight: 700; opacity: .55;
    text-align: right; padding-top: .28rem; font-variant-numeric: tabular-nums; }
.bible .vbody { display: flex; flex-direction: column; gap: .3rem; min-width: 0; }
.bible .v.cols .vbody { display: grid; gap: .75rem; align-items: start;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }
.bible .line { display: flex; gap: .5rem; align-items: baseline; min-width: 0; }
.bible .v.cols .line { flex-direction: column; gap: .25rem; }
.bible .tag { flex: none; font-size: .68rem; font-weight: 700; letter-spacing: .02em;
    padding: .1rem .4rem; border-radius: .3rem; white-space: nowrap;
    border: 1px solid currentColor; opacity: .9; }
.bible .line.rcv .tag { color: %(rcv)s; }
.bible .line.cuv .tag { color: %(cuv)s; }
.bible .line.kjv .tag { color: %(kjv)s; }
.bible .t { font-size: var(--fs); line-height: 1.75; }
.bible .t.zh { font-family: %(zhfont)s; letter-spacing: .01em; }
.bible .t.en { font-family: %(enfont)s; }
.bible .missing { opacity: .4; font-style: italic; font-size: .85rem; }
.bible mark { background: rgba(250,204,21,.45); color: inherit;
    padding: 0 .1em; border-radius: .15em; }
.bible .refhead { font-weight: 700; font-size: .95rem; opacity: .75;
    margin: 1.1rem 0 .1rem; }
</style>
"""

SERIF_ZH = '"Songti SC","Noto Serif CJK SC","Source Han Serif SC","SimSun",serif'
SANS_ZH = '"PingFang SC","Noto Sans CJK SC","Source Han Sans SC","Microsoft YaHei",sans-serif'
SERIF_EN = '"Iowan Old Style","Palatino Linotype",Georgia,serif'
SANS_EN = '-apple-system,"Segoe UI",Roboto,sans-serif'


def inject_css(font_size: int, serif: bool) -> None:
    st.markdown(CSS % {"fs": font_size, "zhfont": SERIF_ZH if serif else SANS_ZH,
                       "enfont": SERIF_EN if serif else SANS_EN, **{k.lower(): v for k, v in ACCENTS.items()}},
                unsafe_allow_html=True)


def scroll_to(verse_no: int) -> None:
    components.html(
        f"""<script>
        (function () {{
          let tries = 0;
          const tick = setInterval(function () {{
            try {{
              const el = window.parent.document.getElementById('v{verse_no}');
              if (el) {{
                el.scrollIntoView({{behavior: 'smooth', block: 'center'}});
                clearInterval(tick);
              }}
            }} catch (e) {{ clearInterval(tick); }}   /* sandboxed: highlight only */
            if (++tries > 25) clearInterval(tick);
          }}, 120);
        }})();
        </script>""", height=0)


# ------------------------------------------------------- reference parsing

@st.cache_data(show_spinner=False)
def book_lookup() -> dict[str, int]:
    table: dict[str, int] = {}
    for book in load_books():
        for key in (book["osis"], book["en"], book["zh_t"], book["zh_s"],
                    book["abbr_t"], book["abbr_s"]):
            table.setdefault(str(key).lower().replace(" ", "").replace(".", ""), book["id"])
    return table


REF_RE = re.compile(r"^\s*(?P<book>(?:[1-3]|[IiVv]{1,3})?\s*[^\d\s:：]+)\s*"
                    r"(?P<chapter>\d+)\s*(?:[:：.]\s*(?P<verse>\d+))?\s*$")


def parse_reference(text: str) -> tuple[int, int, int | None] | None:
    m = REF_RE.match(text or "")
    if not m:
        return None
    key = m["book"].lower().replace(" ", "").replace(".", "")
    lookup = book_lookup()
    book = lookup.get(key) or lookup.get(re.sub(r"[书書]$", "", key))
    if book is None:
        for name, bid in lookup.items():          # prefix match: "gen", "约翰"
            if name.startswith(key) and len(key) >= 3:
                book = bid
                break
    if book is None:
        return None
    chapter = min(int(m["chapter"]), chapter_count(book))
    return book, chapter, int(m["verse"]) if m["verse"] else None


# -------------------------------------------------------------- state

def goto(book: int, chapter: int, verse: int | None = None, *, read: bool = True) -> None:
    st.session_state.book_id = book
    st.session_state.chapter_no = chapter
    st.session_state.anchor = verse
    if read:
        # `mode` is bound to a widget, so it can only be set before that widget
        # is built again — init_state() picks this flag up on the next run.
        st.session_state.want_read = True


def init_state() -> None:
    if st.session_state.pop("want_read", False):
        st.session_state.mode = "对照阅读 Read"
    params = st.query_params
    defaults = {"book_id": 43, "chapter_no": 3, "anchor": None,
                "mode": "对照阅读 Read", "query": ""}
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)
    if "b" in params and "first_load" not in st.session_state:
        try:
            goto(int(params["b"]), int(params.get("c", 1)),
                 int(params["v"]) if params.get("v") else None)
        except (TypeError, ValueError):
            pass
    st.session_state.first_load = True


# ---------------------------------------------------------------- views

def chapter_cells(book: int, chapter: int, chosen: list[dict]) -> tuple[list[int], dict]:
    """load_chapter() with the session's uploaded versions layered on top."""
    verses, cells = load_chapter(book, chapter)
    cells = dict(cells)                      # never mutate a cached value in place
    extra: set[int] = set()
    for meta in chosen:
        for verse, row in local_chapter(meta["code"], book, chapter).items():
            cells[(verse, meta["code"])] = row
            extra.add(verse)
    return (sorted(set(verses) | extra) if extra else verses), cells


def ref_cells(refs: tuple[tuple[int, int, int], ...], chosen: list[dict]) -> dict:
    """load_refs() with the session's uploaded versions layered on top."""
    cells = dict(load_refs(refs))            # never mutate a cached value in place
    for meta in chosen:
        for book, chapter, verse in refs:
            row = local_ref(meta["code"], book, chapter, verse)
            if row is not None:
                cells[(book, chapter, verse, meta["code"])] = row
    return cells


def reading_view(books, versions, chosen, script, lang_mode, side_by_side) -> None:
    book = next(b for b in books if b["id"] == st.session_state.book_id)
    chapter = st.session_state.chapter_no
    verses, cells = chapter_cells(book["id"], chapter, chosen)

    left, mid, right = st.columns([1, 6, 1])
    with left:
        if st.button("← 上一章", use_container_width=True,
                     disabled=(book["id"] == 1 and chapter == 1)):
            if chapter > 1:
                goto(book["id"], chapter - 1)
            else:
                prev = books[[b["id"] for b in books].index(book["id"]) - 1]
                goto(prev["id"], prev["chapters"])
            st.rerun()
    with mid:
        st.markdown(
            f"<h3 style='text-align:center;margin:.1rem 0'>"
            f"{html.escape(book_label(book, script, '双语'))} "
            f"<span style='opacity:.6'>第 {chapter} 章</span></h3>",
            unsafe_allow_html=True)
    with right:
        last = books[-1]
        if st.button("下一章 →", use_container_width=True,
                     disabled=(book["id"] == last["id"] and chapter == last["chapters"])):
            if chapter < book["chapters"]:
                goto(book["id"], chapter + 1)
            else:
                nxt = books[[b["id"] for b in books].index(book["id"]) + 1]
                goto(nxt["id"], 1)
            st.rerun()

    if not verses:
        st.warning("本章没有经文数据。")
        return

    anchor = st.session_state.anchor
    blocks = [render_verse_block(
        v, [(m, verse_text(cells.get((v, m["code"])), m["lang"], script)) for m in chosen],
        anchor=(v == anchor), side_by_side=side_by_side) for v in verses]
    st.markdown(f'<div class="bible">{"".join(blocks)}</div>', unsafe_allow_html=True)

    if anchor in verses:
        scroll_to(anchor)

    st.divider()
    st.caption("  ·  ".join(f"**{v['short']}** — {v['name']}" for v in chosen))


def search_view(books, versions, chosen, script, lang_mode, side_by_side) -> None:
    st.text_input(
        "搜索经文 · Search", key="query", placeholder="输入关键词，或直接输入经节如「约3:16」/「John 3:16」",
        label_visibility="collapsed")
    query = st.session_state.query.strip()

    opt1, opt2, opt3 = st.columns([2, 2, 1])
    scope_books = ["全部 All", "旧约 Old Testament", "新约 New Testament"] + \
        [book_label(b, script, "双语") for b in books]
    scope = opt1.selectbox("范围 Scope", scope_books, index=0)
    search_codes = opt2.multiselect(
        "搜索版本 Search in", [v["code"] for v in chosen],
        default=[v["code"] for v in chosen],
        format_func=lambda c: next(v["short"] for v in versions if v["code"] == c))
    limit = opt3.number_input("上限", 10, MAX_RESULTS, 50, step=10)

    if not query:
        st.info("在上面的搜索框输入关键词。中文简繁体皆可，英文不分大小写；"
                "多个词以空格分隔表示同时出现。")
        return

    ref = parse_reference(query)
    if ref:
        book = next(b for b in books if b["id"] == ref[0])
        label = f"{book_label(book, script, '双语')} {ref[1]}" + (f":{ref[2]}" if ref[2] else "")
        if st.button(f"📖 跳转到 {label}", type="primary"):
            goto(*ref)
            st.rerun()

    testament = {"旧约 Old Testament": "OT", "新约 New Testament": "NT"}.get(scope, "ALL")
    book_filter = None
    if scope not in ("全部 All", "旧约 Old Testament", "新约 New Testament"):
        book_filter = next(b["id"] for b in books
                           if book_label(b, script, "双语") == scope)

    store = local_store()
    db_codes = tuple(c for c in search_codes if c not in store)
    hits = set(search_verses(query, db_codes, testament, book_filter, int(limit)))
    for code in search_codes:
        if code in store:
            hits.update(local_search(code, query.split(), testament, book_filter))
    capped = len(hits) > int(limit)
    hits = sorted(hits)[:int(limit)]
    if not hits:
        st.warning(f"没有找到「{query}」。")
        return

    st.success(f"找到 {len(hits)} 处" + ("（已达上限，可缩小范围或提高上限）"
                                        if capped or len(hits) == int(limit) else ""))
    cells = ref_cells(tuple(hits), chosen)
    terms = query.split()
    by_id = {b["id"]: b for b in books}

    for book_id, chapter, verse in hits:
        book = by_id[book_id]
        label = f"{book_label(book, script, '双语')} {chapter}:{verse}"
        head, jump = st.columns([5, 1])
        head.markdown(f'<div class="bible"><div class="refhead">{html.escape(label)}</div></div>',
                      unsafe_allow_html=True)
        jump.button("前往 →", key=f"go-{book_id}-{chapter}-{verse}",
                    on_click=goto, args=(book_id, chapter, verse))
        block = render_verse_block(
            verse,
            [(m, verse_text(cells.get((book_id, chapter, verse, m["code"])), m["lang"], script))
             for m in chosen],
            anchor=False, side_by_side=side_by_side, terms=terms)
        st.markdown(f'<div class="bible">{block}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------- main

def upload_panel(versions: list[dict]) -> None:
    """Sidebar control for loading a copyrighted version from the user's own file."""
    store = local_store()
    slots = [v for v in versions if not v["in_db"]] or [v for v in versions if v["lang"] == "zh"]
    loaded = [v for v in versions if v["code"] in store]

    with st.expander("载入恢复本 Load Recovery Version",
                     expanded=not loaded and bool([v for v in versions if not v["available"]])):
        st.caption(
            "恢复本版权属水流职事站，本站不附带其经文。请上传你自己的副本 — "
            "文件只保存在你这次浏览的会话内存中，不写入服务器，也不会被其他访客看到。")
        code = slots[0]["code"] if len(slots) == 1 else st.selectbox(
            "填入版本 Slot", [v["code"] for v in slots],
            format_func=lambda c: next(v["short"] for v in versions if v["code"] == c))

        for v in loaded:
            entry = store[v["code"]]
            st.success(f"{v['short']}：{len(entry['rows']):,} 节 · {entry['name']}", icon="✅")
        if loaded and st.button("清除已载入 Clear", use_container_width=True):
            store.clear()
            st.rerun()

        upload = st.file_uploader(
            "经文文件 File", type=UPLOAD_TYPES, key="rcv_upload",
            help="CSV/TSV（含 book/chapter/verse/text 表头）、JSON、"
                 "MySword/e-Sword 模块，或每行一节的 TXT。")
        strip_notes = st.checkbox("去除注解标记 Strip footnote markers", value=True)
        if upload is not None and st.button("导入 Import", type="primary",
                                            use_container_width=True):
            try:
                with st.spinner("解析中…"):
                    info = ingest_upload(code, upload.name, upload.getvalue(), strip_notes)
            except (ValueError, OSError, UnicodeDecodeError) as exc:
                st.error(f"导入失败：{exc}")
            else:
                if info["unknown"]:
                    st.warning("无法识别的书卷名（已跳过）：" + "、".join(info["unknown"]))
                if info["skipped"]:
                    st.warning(f"{info['skipped']} 行章节号非数字，已跳过。")
                st.toast(f"已载入 {info['verses']:,} 节，{info['books']} 卷书。", icon="📖")
                st.rerun()

        st.caption("要长期保存（仅限自己的电脑），改用："
                   "`python scripts/import_rcv.py <文件>`")


def main() -> None:
    init_state()
    books = load_books()
    versions = versions_now()

    with st.sidebar:
        st.title("📖 三版本圣经对照")
        st.caption("Recovery Version · 和合本 · King James")

        available = [v for v in versions if v["available"]]
        codes = st.multiselect(
            "版本 Versions", [v["code"] for v in available],
            default=[v["code"] for v in available],
            format_func=lambda c: next(v["short"] for v in versions if v["code"] == c))
        chosen = [v for v in versions if v["code"] in codes]

        missing = [v for v in versions if not v["available"]]
        if missing:
            st.warning("未收录：" + "、".join(v["short"] for v in missing) +
                       "（可在下方「载入恢复本」中导入）", icon="⚠️")
        upload_panel(versions)

        st.divider()
        st.subheader("导航 Navigate")
        script = st.radio("字体 Script", ["简体", "繁體"], horizontal=True,
                          label_visibility="collapsed")
        names = [book_label(b, script, "双语") for b in books]
        index = [b["id"] for b in books].index(st.session_state.book_id)
        picked = st.selectbox("书卷 Book", names, index=index)
        book = books[names.index(picked)]
        if book["id"] != st.session_state.book_id:
            goto(book["id"], 1)
            st.rerun()

        total = book["chapters"]
        chapter = st.selectbox("章 Chapter", range(1, total + 1),
                               index=min(st.session_state.chapter_no, total) - 1,
                               format_func=lambda c: f"第 {c} 章")
        if chapter != st.session_state.chapter_no:
            goto(book["id"], chapter)
            st.rerun()

        verse_nos, _ = chapter_cells(book["id"], chapter, chosen)
        if verse_nos:
            current = st.session_state.anchor or verse_nos[0]
            target = st.number_input("节 Verse", min_value=verse_nos[0],
                                     max_value=verse_nos[-1],
                                     value=min(max(current, verse_nos[0]), verse_nos[-1]))
            if st.button("跳到该节 Go", use_container_width=True):
                goto(book["id"], chapter, int(target))
                st.rerun()

        st.divider()
        with st.expander("显示设置 Display", expanded=False):
            layout = st.radio("排版 Layout", ["逐节堆叠 Stacked", "并排 Side-by-side"],
                              help="堆叠：三个版本上下排列，逐节对照。并排：三栏并列。")
            font_size = st.slider("字号 Font size", 13, 26, 17)
            serif = st.toggle("衬线字体 Serif", value=True)

        st.divider()
        if st.button("重新载入数据 Reload data", use_container_width=True,
                     help="导入新版本后点此刷新缓存"):
            st.cache_data.clear()
            st.cache_resource.clear()
            st.rerun()
        for v in versions:
            st.caption(f"**{v['short']}** · {v['copyright']}")

    inject_css(font_size, serif)
    st.query_params.update({"b": str(st.session_state.book_id),
                            "c": str(st.session_state.chapter_no),
                            "v": str(st.session_state.anchor or "")})

    if not chosen:
        st.info("请在左侧至少选择一个版本。")
        return

    mode = st.radio("模式", ["对照阅读 Read", "搜索 Search"], key="mode",
                    horizontal=True, label_visibility="collapsed")
    view = search_view if mode == "搜索 Search" else reading_view
    view(books, versions, chosen, script, "双语", layout.startswith("并排"))


if __name__ == "__main__":
    main()
