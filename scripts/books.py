"""Canonical 66-book metadata shared by the build scripts and the app."""

# (order, osis, english, traditional Chinese, testament)
BOOKS = [
    (1, "Gen", "Genesis", "創世記", "OT"),
    (2, "Exod", "Exodus", "出埃及記", "OT"),
    (3, "Lev", "Leviticus", "利未記", "OT"),
    (4, "Num", "Numbers", "民數記", "OT"),
    (5, "Deut", "Deuteronomy", "申命記", "OT"),
    (6, "Josh", "Joshua", "約書亞記", "OT"),
    (7, "Judg", "Judges", "士師記", "OT"),
    (8, "Ruth", "Ruth", "路得記", "OT"),
    (9, "1Sam", "I Samuel", "撒母耳記上", "OT"),
    (10, "2Sam", "II Samuel", "撒母耳記下", "OT"),
    (11, "1Kgs", "I Kings", "列王紀上", "OT"),
    (12, "2Kgs", "II Kings", "列王紀下", "OT"),
    (13, "1Chr", "I Chronicles", "歷代志上", "OT"),
    (14, "2Chr", "II Chronicles", "歷代志下", "OT"),
    (15, "Ezra", "Ezra", "以斯拉記", "OT"),
    (16, "Neh", "Nehemiah", "尼希米記", "OT"),
    (17, "Esth", "Esther", "以斯帖記", "OT"),
    (18, "Job", "Job", "約伯記", "OT"),
    (19, "Ps", "Psalms", "詩篇", "OT"),
    (20, "Prov", "Proverbs", "箴言", "OT"),
    (21, "Eccl", "Ecclesiastes", "傳道書", "OT"),
    (22, "Song", "Song of Solomon", "雅歌", "OT"),
    (23, "Isa", "Isaiah", "以賽亞書", "OT"),
    (24, "Jer", "Jeremiah", "耶利米書", "OT"),
    (25, "Lam", "Lamentations", "耶利米哀歌", "OT"),
    (26, "Ezek", "Ezekiel", "以西結書", "OT"),
    (27, "Dan", "Daniel", "但以理書", "OT"),
    (28, "Hos", "Hosea", "何西阿書", "OT"),
    (29, "Joel", "Joel", "約珥書", "OT"),
    (30, "Amos", "Amos", "阿摩司書", "OT"),
    (31, "Obad", "Obadiah", "俄巴底亞書", "OT"),
    (32, "Jonah", "Jonah", "約拿書", "OT"),
    (33, "Mic", "Micah", "彌迦書", "OT"),
    (34, "Nah", "Nahum", "那鴻書", "OT"),
    (35, "Hab", "Habakkuk", "哈巴谷書", "OT"),
    (36, "Zeph", "Zephaniah", "西番雅書", "OT"),
    (37, "Hag", "Haggai", "哈該書", "OT"),
    (38, "Zech", "Zechariah", "撒迦利亞書", "OT"),
    (39, "Mal", "Malachi", "瑪拉基書", "OT"),
    (40, "Matt", "Matthew", "馬太福音", "NT"),
    (41, "Mark", "Mark", "馬可福音", "NT"),
    (42, "Luke", "Luke", "路加福音", "NT"),
    (43, "John", "John", "約翰福音", "NT"),
    (44, "Acts", "Acts", "使徒行傳", "NT"),
    (45, "Rom", "Romans", "羅馬書", "NT"),
    (46, "1Cor", "I Corinthians", "哥林多前書", "NT"),
    (47, "2Cor", "II Corinthians", "哥林多後書", "NT"),
    (48, "Gal", "Galatians", "加拉太書", "NT"),
    (49, "Eph", "Ephesians", "以弗所書", "NT"),
    (50, "Phil", "Philippians", "腓立比書", "NT"),
    (51, "Col", "Colossians", "歌羅西書", "NT"),
    (52, "1Thess", "I Thessalonians", "帖撒羅尼迦前書", "NT"),
    (53, "2Thess", "II Thessalonians", "帖撒羅尼迦後書", "NT"),
    (54, "1Tim", "I Timothy", "提摩太前書", "NT"),
    (55, "2Tim", "II Timothy", "提摩太後書", "NT"),
    (56, "Titus", "Titus", "提多書", "NT"),
    (57, "Phlm", "Philemon", "腓利門書", "NT"),
    (58, "Heb", "Hebrews", "希伯來書", "NT"),
    (59, "Jas", "James", "雅各書", "NT"),
    (60, "1Pet", "I Peter", "彼得前書", "NT"),
    (61, "2Pet", "II Peter", "彼得後書", "NT"),
    (62, "1John", "I John", "約翰壹書", "NT"),
    (63, "2John", "II John", "約翰貳書", "NT"),
    (64, "3John", "III John", "約翰參書", "NT"),
    (65, "Jude", "Jude", "猶大書", "NT"),
    (66, "Rev", "Revelation of John", "啟示錄", "NT"),
]

# English source-CSV name -> book id
BY_SOURCE_NAME = {en: i for i, _osis, en, _zh, _t in BOOKS}
BY_OSIS = {osis.lower(): i for i, osis, _en, _zh, _t in BOOKS}

# Extra aliases accepted by the reference parser / importers.
ALIASES = {
    "song of songs": 22, "canticles": 22, "psalm": 19,
    "revelation": 66, "the revelation": 66, "apocalypse": 66,
    "1 samuel": 9, "2 samuel": 10, "1 kings": 11, "2 kings": 12,
    "1 chronicles": 13, "2 chronicles": 14, "1 corinthians": 46,
    "2 corinthians": 47, "1 thessalonians": 52, "2 thessalonians": 53,
    "1 timothy": 54, "2 timothy": 55, "1 peter": 60, "2 peter": 61,
    "1 john": 62, "2 john": 63, "3 john": 64,
    # 一/壹, 二/貳/贰, 三/參/参/叁 all appear as the Johannine epistle numerals
    # depending on the edition; ABBR_ZH carries 約壹/約貳/約參, these are the rest.
    "约一": 62, "約一": 62, "约二": 63, "約二": 63, "约三": 64, "約三": 64,
    "约叁": 64, "約叁": 64, "约参": 64,
}

# Standard Chinese abbreviations (和合本 / 恢復本 share these), traditional.
ABBR_ZH = [
    "創", "出", "利", "民", "申", "書", "士", "得", "撒上", "撒下", "王上", "王下",
    "代上", "代下", "拉", "尼", "斯", "伯", "詩", "箴", "傳", "歌", "賽", "耶",
    "哀", "結", "但", "何", "珥", "摩", "俄", "拿", "彌", "鴻", "哈", "番", "該",
    "亞", "瑪", "太", "可", "路", "約", "徒", "羅", "林前", "林後", "加", "弗",
    "腓", "西", "帖前", "帖後", "提前", "提後", "多", "門", "來", "雅", "彼前",
    "彼後", "約壹", "約貳", "約參", "猶", "啟",
]
assert len(ABBR_ZH) == 66


def lookup_table(t2s=None):
    """Every accepted spelling of a book name -> book id (1..66)."""
    table = {}

    def add(key, bid):
        key = str(key).strip().lower().replace(" ", "").replace(".", "")
        if key:
            table.setdefault(key, bid)

    for (bid, osis, en, zh, _t), abbr in zip(BOOKS, ABBR_ZH):
        for key in (bid, osis, en, zh, abbr):
            add(key, bid)
        if t2s:
            add(t2s(zh), bid)
            add(t2s(abbr), bid)
    for alias, bid in ALIASES.items():
        add(alias, bid)
    return table
