#!/usr/bin/env python3
"""從 corpus/*.txt 產生 Cloudflare D1 的 schema 與 seed。

- db/schema.sql：表格定義（含 FTS5 全文檢索虛擬表）
- db/seed.sql：topics / turns（含 ruby 標注 JSON）/ vocab / turns_fts

ruby（羅馬拼音）產生規則：
- 中文：逐字漢語拼音（pypinyin，有快取）
- 日文：逐詞羅馬音（假名→Hepburn 羅馬音；含漢字詞用人工讀音表）
- 韓文：逐詞 Revised Romanization（Hangul 音節分解，純演算法）

用法：
    python3 code/build_site.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus"
OUT = ROOT / "cloudflare" / "db"
CACHE = ROOT / "code" / "data" / "pinyin_cache.json"

LANGS = ["zh", "en", "fr", "ja", "ko"]
LANG_LABEL = {"zh": "中", "en": "英", "fr": "法", "ja": "日", "ko": "韓"}
TOPIC_TITLES = {
    "dialog": ("綜合日常", "Everyday"),
    "family": ("家庭", "Family"),
    "school": ("學校", "School"),
    "morning": ("早晨", "Morning"),
    "outing": ("外出", "Outing"),
    "transport": ("交通", "Transport"),
    "airport": ("機場", "Airport"),
    "friends": ("交友", "Friends"),
    "market": ("市場購物", "Market"),
    "restaurant": ("餐廳", "Restaurant"),
    "hospital": ("醫院", "Hospital"),
    "work": ("工作", "Work"),
    "phone": ("電話與訊息", "Phone"),
    "birthday": ("生日", "Birthday"),
    "weather": ("天氣", "Weather"),
}

# ---------------------------------------------------------------- 中文拼音

def load_pinyin() -> dict:
    if CACHE.exists():
        return json.loads(CACHE.read_text(encoding="utf-8"))
    cache = {}
    try:
        from pypinyin import pinyin, Style
    except ImportError:
        print("需要 pypinyin（pip install pypinyin），且首次執行要有 code/data/ 快取", file=sys.stderr)
        raise
    return cache, pinyin, Style


def zh_ruby(text: str, cache: dict, py_fn, style) -> list:
    """回傳 [[char, pinyin], ...]；非漢字 pinyin 為空字串。"""
    out = []
    for ch in text:
        if "\u4e00" <= ch <= "\u9fff":
            if ch not in cache:
                if py_fn is None:
                    raise ValueError(f"缺拼音快取且沒有 pypinyin：{ch!r}（請先刪除快取重跑一次）")
                cache[ch] = py_fn(ch, style=style)[0][0]
            out.append([ch, cache[ch]])
        else:
            out.append([ch, ""])
    return out


# ---------------------------------------------------------------- 日文羅馬音

JA_TOKENS = {
    "1人": "ひとり", "あの日は": "あのひは", "お金を": "おかねを", "ご飯が": "ごはんが",
    "とり肉は": "とりにくは", "とり肉を": "とりにくを", "下に": "したに",
    "人": "ひと", "人が": "ひとが", "人だ": "ひとだ", "人だけだ": "ひとだけだ",
    "人で": "ひとで", "人に": "ひとに", "作れる": "つくれる", "先に": "さきに",
    "先生が": "せんせいが", "先生に": "せんせいに", "先生は": "せんせいは",
    "力": "ちから", "半分は": "はんぶんは", "南へ": "みなみへ",
    "友だちが": "ともだちが", "友だちだ": "ともだちだ", "友だちと": "ともだちと",
    "友だちを": "ともだちを", "句": "く", "句は": "くは", "句を": "くを", "回": "かい",
    "外を": "そとを", "多い": "おおい", "多く": "おおく", "多くの": "おおくの",
    "大きい": "おおきい", "大きいから": "おおきいから", "大きくて": "おおきくて",
    "好好に": "ちゃんと", "家に": "いえに", "家の": "いえの", "家へ": "いえへ",
    "小さい": "ちいさい", "小さな": "ちいさな", "少し": "すこし",
    "少ないから": "すくないから", "山と": "やまと", "年老いたら": "としおいたら",
    "店が": "みせが", "店で": "みせで", "店に": "みせに", "店へ": "みせへ",
    "手で": "てで", "教えて": "おしえて", "教えるのが": "おしえるのが",
    "新しい": "あたらしい", "方法が": "ほうほうが", "日": "ひ", "日ご": "ひご",
    "日に": "ひに", "日を": "ひを", "早く": "はやく", "明るい": "あかるい",
    "明年も": "らいねんも", "星が": "ほしが", "星の": "ほしの",
    "時間が": "じかんが", "書く": "かく", "服と": "ふくと", "服に": "ふくに",
    "服は": "ふくは", "服も": "ふくも", "服を": "ふくを", "木と": "きと", "木に": "きに",
    "果物と": "くだものと", "水が": "みずが", "水と": "みずと", "水の": "みずの",
    "水を": "みずを", "海": "うみ", "海に": "うみに", "海が": "うみが", "海だ": "うみだ",
    "海の": "うみの", "海は": "うみは", "海へ": "うみへ", "海まで": "うみまで",
    "海を": "うみを", "生きる": "いきる", "病は": "やまいは", "知らない": "しらない",
    "空へ": "そらへ", "笑いません": "わらいません", "笑って": "わらって",
    "第": "だい", "紙と": "かみと", "老人が": "ろうじんが", "花が": "はなが",
    "花を": "はなを", "茶が": "ちゃが", "茶と": "ちゃと", "茶を": "ちゃを",
    "話す": "はなす", "話そう": "はなそう", "買いに": "かいに", "買わない": "かわない",
    "車が": "くるまが", "車で": "くるまで", "車を": "くるまを", "近い": "ちかい",
    "道の": "みちの", "道理が": "どうりが", "遠い": "とおい", "重要だ": "じゅうようだ",
    "門で": "もんで", "門の": "もんの", "門を": "もんを", "電話が": "でんわが",
    "電話して": "でんわして", "電話する": "でんわする", "電話で": "でんわで",
    "音が": "おとが", "風が": "かぜが", "魚が": "さかなが", "鳥が": "とりが",
    "鳥だ": "とりだ",
}

JA_KANA = {
    "あ": "a", "い": "i", "う": "u", "え": "e", "お": "o",
    "か": "ka", "き": "ki", "く": "ku", "け": "ke", "こ": "ko",
    "が": "ga", "ぎ": "gi", "ぐ": "gu", "げ": "ge", "ご": "go",
    "さ": "sa", "し": "shi", "す": "su", "せ": "se", "そ": "so",
    "ざ": "za", "じ": "ji", "ず": "zu", "ぜ": "ze", "ぞ": "zo",
    "た": "ta", "ち": "chi", "つ": "tsu", "て": "te", "と": "to",
    "だ": "da", "ぢ": "ji", "づ": "zu", "で": "de", "ど": "do",
    "な": "na", "に": "ni", "ぬ": "nu", "ね": "ne", "の": "no",
    "は": "ha", "ひ": "hi", "ふ": "fu", "へ": "he", "ほ": "ho",
    "ば": "ba", "び": "bi", "ぶ": "bu", "べ": "be", "ぼ": "bo",
    "ぱ": "pa", "ぴ": "pi", "ぷ": "pu", "ぺ": "pe", "ぽ": "po",
    "ま": "ma", "み": "mi", "む": "mu", "め": "me", "も": "mo",
    "や": "ya", "ゆ": "yu", "よ": "yo",
    "ら": "ra", "り": "ri", "る": "ru", "れ": "re", "ろ": "ro",
    "わ": "wa", "ゐ": "i", "ゑ": "e", "を": "o", "ん": "n",
    "ぁ": "a", "ぃ": "i", "ぅ": "u", "ぇ": "e", "ぉ": "o",
    "ア": "a", "イ": "i", "ウ": "u", "エ": "e", "オ": "o",
    "カ": "ka", "キ": "ki", "ク": "ku", "ケ": "ke", "コ": "ko",
    "ガ": "ga", "ギ": "gi", "グ": "gu", "ゲ": "ge", "ゴ": "go",
    "サ": "sa", "シ": "shi", "ス": "su", "セ": "se", "ソ": "so",
    "ザ": "za", "ジ": "ji", "ズ": "zu", "ゼ": "ze", "ゾ": "zo",
    "タ": "ta", "チ": "chi", "ツ": "tsu", "テ": "te", "ト": "to",
    "ダ": "da", "ヂ": "ji", "ヅ": "zu", "デ": "de", "ド": "do",
    "ナ": "na", "ニ": "ni", "ヌ": "nu", "ネ": "ne", "ノ": "no",
    "ハ": "ha", "ヒ": "hi", "フ": "fu", "ヘ": "he", "ホ": "ho",
    "バ": "ba", "ビ": "bi", "ブ": "bu", "ベ": "be", "ボ": "bo",
    "パ": "pa", "ピ": "pi", "プ": "pu", "ペ": "pe", "ポ": "po",
    "マ": "ma", "ミ": "mi", "ム": "mu", "メ": "me", "モ": "mo",
    "ヤ": "ya", "ユ": "yu", "ヨ": "yo",
    "ラ": "ra", "リ": "ri", "ル": "ru", "レ": "re", "ロ": "ro",
    "ワ": "wa", "ヲ": "o", "ン": "n", "ヴ": "vu",
    "ァ": "a", "ィ": "i", "ゥ": "u", "ェ": "e", "ォ": "o",
    "ヮ": "wa",
}
JA_DIGRAPH = {
    "きゃ": "kya", "きゅ": "kyu", "きょ": "kyo",
    "しゃ": "sha", "しゅ": "shu", "しょ": "sho",
    "ちゃ": "cha", "ちゅ": "chu", "ちょ": "cho",
    "にゃ": "nya", "にゅ": "nyu", "にょ": "nyo",
    "ひゃ": "hya", "ひゅ": "hyu", "ひょ": "hyo",
    "みゃ": "mya", "みゅ": "myu", "みょ": "myo",
    "りゃ": "rya", "りゅ": "ryu", "りょ": "ryo",
    "ぎゃ": "gya", "ぎゅ": "gyu", "ぎょ": "gyo",
    "じゃ": "ja", "じゅ": "ju", "じょ": "jo",
    "びゃ": "bya", "びゅ": "byu", "びょ": "byo",
    "ぴゃ": "pya", "ぴゅ": "pyu", "ぴょ": "pyo",
    "ふぁ": "fa", "ふぃ": "fi", "ふぇ": "fe", "ふぉ": "fo",
    "てぃ": "ti", "でぃ": "di", "とぅ": "tu", "どぅ": "du",
    "うぇ": "we", "うぃ": "wi", "シェ": "she", "チェ": "che",
    "ジェ": "je", "ファ": "fa", "フィ": "fi", "フェ": "fe", "フォ": "fo",
    "ティ": "ti", "ディ": "di", "トゥ": "tu", "ドゥ": "du",
    "キャ": "kya", "キュ": "kyu", "キョ": "kyo",
    "シャ": "sha", "シュ": "shu", "ショ": "sho",
    "チャ": "cha", "チュ": "chu", "チョ": "cho",
    "ニャ": "nya", "ニュ": "nyu", "ニョ": "nyo",
    "ヒャ": "hya", "ヒュ": "hyu", "ヒョ": "hyo",
    "ミャ": "mya", "ミュ": "myu", "ミョ": "myo",
    "リャ": "rya", "リュ": "ryu", "リョ": "ryo",
    "ギャ": "gya", "ギュ": "gyu", "ギョ": "gyo",
    "ジャ": "ja", "ジュ": "ju", "ジョ": "jo",
    "ビャ": "bya", "ビュ": "byu", "ビョ": "byo",
    "ピャ": "pya", "ピュ": "pyu", "ピョ": "pyo",
}
SMALL_Y = {"ゃ", "ゅ", "ょ", "ャ", "ュ", "ョ"}
PUNCT = "。、！？…「」『』（）・，～“”\"'"


def kana_to_romaji(text: str) -> str:
    """假名 → Hepburn 羅馬音（含促音、長音、撥音規則）。"""
    out = []
    i = 0
    n = len(text)
    while i < n:
        two = text[i:i + 2]
        if two in JA_DIGRAPH:
            out.append(JA_DIGRAPH[two])
            i += 2
            continue
        ch = text[i]
        if ch == "っ" or ch == "ッ":
            nxt = ""
            j = i + 1
            if j < n:
                t2 = text[j:j + 2]
                nxt = JA_DIGRAPH.get(t2) or JA_KANA.get(text[j], "")
            if nxt:
                out.append(nxt[0])
            i += 1
            continue
        if ch == "ー":
            if out:
                last = out[-1]
                m = re.search(r"[aiueo]$", last)
                out[-1] = last + (m.group(0) if m else "u")
            i += 1
            continue
        if ch in JA_KANA:
            r = JA_KANA[ch]
            # 助詞：語尾の は→wa、へ→e
            nxt = text[i + 1] if i + 1 < n else ""
            if ch == "は" and (nxt == "" or nxt in PUNCT or nxt == " "):
                r = "wa"
            if ch == "へ" and (nxt == "" or nxt in PUNCT or nxt == " "):
                r = "e"
            # 撥音：ん + b/p/m → m
            if r == "n" and i + 1 < n:
                nxt2 = JA_KANA.get(text[i + 1], "")
                if nxt2 and nxt2[0] in "bpm":
                    r = "m"
            out.append(r)
            i += 1
            continue
        out.append(ch)  # 拉丁、數字、標點原樣保留
        i += 1
    return "".join(out)


def ja_reading(token: str) -> str:
    core = token.strip(PUNCT)
    return JA_TOKENS.get(core, core)


JA_WORD = re.compile(r"[\u4e00-\u9fff\u3040-\u30ff\u3400-\u4dbf a-zA-Z0-9'’]+")


def ja_ruby(text: str) -> list:
    """回傳 [[token, romaji], ...]；標點自成一個無讀音的片段。"""
    out = []
    for tok in text.split(" "):
        if not tok:
            continue
        pos = 0
        for m in JA_WORD.finditer(tok):
            if m.start() > pos:
                out.append([tok[pos:m.start()], ""])
            core = m.group(0)
            if re.search(r"[\u4e00-\u9fff]", core) and core not in JA_TOKENS:
                raise ValueError(f"缺日文讀音：{core!r}（原句：{text!r}）")
            out.append([core, kana_to_romaji(JA_TOKENS.get(core, core))])
            pos = m.end()
        if pos < len(tok):
            out.append([tok[pos:], ""])
    return out


# ---------------------------------------------------------------- 韓文羅馬拼音

KO_CHO = ["g", "kk", "n", "d", "tt", "r", "m", "b", "pp", "s", "ss", "", "j", "jj", "ch", "k", "t", "p", "h"]
KO_JUNG = ["a", "ae", "ya", "yae", "eo", "e", "yeo", "ye", "o", "wa", "wae", "oe", "yo", "u", "wo", "we", "wi", "yu", "eu", "ui", "i"]
KO_JONG = ["", "k", "k", "k", "n", "n", "n", "t", "l", "k", "m", "l", "l", "l", "l", "l", "m", "p", "p", "t", "t", "ng", "t", "t", "k", "t", "p", "t"]


def ko_word_romaji(word: str) -> str:
    out = []
    for ch in word:
        code = ord(ch)
        if 0xAC00 <= code <= 0xD7A3:
            s = code - 0xAC00
            cho, jung, jong = s // (21 * 28), (s // 28) % 21, s % 28
            out.append(KO_CHO[cho] + KO_JUNG[jung] + KO_JONG[jong])
        else:
            out.append(ch)
    return "".join(out)


def ko_ruby(text: str) -> list:
    out = []
    for w in text.split(" "):
        if not w:
            continue
        m = re.match(r"^([^.,!?…]*)([.,!?…]*)$", w)
        core, punct = m.group(1), m.group(2)
        if core:
            out.append([core, ko_word_romaji(core)])
        if punct:
            out.append([punct, ""])
    return out


# ---------------------------------------------------------------- 語料解析

TURN = re.compile(r"^(中|英|法|日|韓) ([AB]): (.*)$")
LABEL = {"中": "zh", "英": "en", "法": "fr", "日": "ja", "韓": "ko"}


def parse_corpus() -> dict:
    topics = {}
    for path in sorted(CORPUS.glob("*.txt")):
        turns = []
        cur = None
        for line in path.read_text(encoding="utf-8").split("\n"):
            if line.startswith("#") or not line.strip():
                continue
            m = TURN.match(line)
            if not m:
                raise ValueError(f"{path.name}: 格式錯誤 {line!r}")
            lang, speaker, text = LABEL[m.group(1)], m.group(2), m.group(3).strip()
            if lang == "zh":
                if cur:
                    turns.append(cur)
                cur = {"speaker": speaker, "text": {}}
            if cur is None or cur["speaker"] != speaker:
                raise ValueError(f"{path.name}: 語言順序錯誤 {line!r}")
            cur["text"][lang] = text
            if len(cur["text"]) == 5:
                turns.append(cur)
                cur = None
        if cur:
            turns.append(cur)
        if path.stem not in TOPIC_TITLES:
            raise ValueError(f"未知主題 {path.stem}")
        zh, en = TOPIC_TITLES[path.stem]
        topics[path.stem] = {"slug": path.stem, "zh": zh, "en": en, "turns": turns}
    return topics


# ---------------------------------------------------------------- 搜尋索引

CJK = re.compile(r"[\u4e00-\u9fff\u3040-\u30ff\u3400-\u4dbf]")


def fts_body(lang: str, text: str) -> str:
    if lang in ("zh", "ja"):
        # CJK 逐字切開（unicode61 不斷 CJK），拉丁字詞原樣保留
        out = []
        for ch in text:
            if CJK.match(ch) or ch == " ":
                out.append(" ")
                if CJK.match(ch):
                    out.append(ch)
            elif ch.isalnum() or ch == "'":
                out.append(ch.lower())
        return " ".join("".join(out).split())
    # en / fr / ko：以詞為單位
    if lang == "en":
        words = re.findall(r"[a-z0-9']+", text.lower())
    elif lang == "fr":
        words = re.findall(r"[a-zà-öø-ÿœ0-9']+", text.lower())
    else:
        words = re.findall(r"[가-힣a-z0-9]+", text.lower())
    return " ".join(words)


def extract_vocab(topics: dict) -> list:
    vocab = {}

    def add(lang, term, reading):
        term = term.strip()
        if not term:
            return
        key = (lang, term)
        if key not in vocab:
            vocab[key] = reading

    for t in topics.values():
        for turn in t["turns"]:
            zh_pairs = turn["ruby"]["zh"]
            for ch, pinyin in zh_pairs:
                if "\u4e00" <= ch <= "\u9fff":
                    add("zh", ch, pinyin)
            for tok, romaji in turn["ruby"]["ja"]:
                core = tok.strip(PUNCT)
                if core:
                    add("ja", core, romaji)
            for w, romaji in turn["ruby"]["ko"]:
                core = re.sub(r"[.,!?…]", "", w)
                if core:
                    add("ko", core, romaji)
            for lang, rx in (("en", r"[a-z']+"), ("fr", r"[a-zà-öø-ÿœ']+")):
                for w in re.findall(rx, turn["text"][lang].lower()):
                    add(lang, w, "")
    return [{"lang": k[0], "term": k[1], "reading": v} for k, v in sorted(vocab.items())]


# ---------------------------------------------------------------- SQL 產生

def sql_str(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def main():
    cache = {}
    py_fn = style = None
    if CACHE.exists():
        cache = json.loads(CACHE.read_text(encoding="utf-8"))
    else:
        try:
            from pypinyin import pinyin as _py, Style as _st
            py_fn, style = _py, _st
        except ImportError:
            print("警告：沒有 pypinyin 也沒有快取，中文 ruby 會是空的", file=sys.stderr)

    topics = parse_corpus()

    schema = """-- mini-lang D1 schema（SQLite / FTS5）
CREATE TABLE IF NOT EXISTS topics (
  id       INTEGER PRIMARY KEY,
  slug     TEXT NOT NULL UNIQUE,
  title_zh TEXT NOT NULL,
  title_en TEXT NOT NULL,
  ord      INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS turns (
  id       INTEGER PRIMARY KEY,
  topic_id INTEGER NOT NULL REFERENCES topics(id),
  idx      INTEGER NOT NULL,
  speaker  TEXT NOT NULL,
  zh TEXT NOT NULL, en TEXT NOT NULL, fr TEXT NOT NULL,
  ja TEXT NOT NULL, ko TEXT NOT NULL,
  ruby     TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_turns_topic ON turns(topic_id, idx);
CREATE TABLE IF NOT EXISTS vocab (
  id      INTEGER PRIMARY KEY,
  lang    TEXT NOT NULL,
  term    TEXT NOT NULL,
  reading TEXT NOT NULL DEFAULT ''
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_vocab ON vocab(lang, term);
CREATE TABLE IF NOT EXISTS progress (
  device  TEXT NOT NULL,
  turn_id INTEGER NOT NULL REFERENCES turns(id),
  stars   INTEGER NOT NULL DEFAULT 0,
  ts      INTEGER NOT NULL,
  PRIMARY KEY (device, turn_id)
);
CREATE TABLE IF NOT EXISTS quiz_log (
  id      INTEGER PRIMARY KEY,
  device  TEXT NOT NULL,
  turn_id INTEGER NOT NULL,
  correct INTEGER NOT NULL,
  ts      INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_quiz_device ON quiz_log(device, ts);

-- 全文檢索：unicode61；中文／日文的 body 已在 build 期逐字切開
CREATE VIRTUAL TABLE IF NOT EXISTS turns_fts USING fts5(
  turn_id UNINDEXED,
  lang    UNINDEXED,
  body,
  tokenize = "unicode61 remove_diacritics 2"
);
"""
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "schema.sql").write_text(schema, encoding="utf-8")

    lines = ["-- 由 code/build_site.py 產生，請勿手改"]
    tid = 0
    turn_id = 0
    for slug, t in topics.items():
        tid += 1
        lines.append(
            f"INSERT OR REPLACE INTO topics(id,slug,title_zh,title_en,ord) VALUES({tid},{sql_str(slug)},{sql_str(t['zh'])},{sql_str(t['en'])},{tid});"
        )
        for idx, turn in enumerate(t["turns"], 1):
            turn_id += 1
            turn["ruby"] = {
                "zh": zh_ruby(turn["text"]["zh"], cache, py_fn, style),
                "ja": ja_ruby(turn["text"]["ja"]),
                "ko": ko_ruby(turn["text"]["ko"]),
            }
            ruby = json.dumps(turn["ruby"], ensure_ascii=False, separators=(",", ":"))
            text = turn["text"]
            lines.append(
                f"INSERT OR REPLACE INTO turns(id,topic_id,idx,speaker,zh,en,fr,ja,ko,ruby) VALUES("
                f"{turn_id},{tid},{idx},{sql_str(turn['speaker'])},"
                f"{sql_str(text['zh'])},{sql_str(text['en'])},{sql_str(text['fr'])},{sql_str(text['ja'])},{sql_str(text['ko'])},{sql_str(ruby)});"
            )
            for lang in LANGS:
                body = fts_body(lang, text[lang])
                if body:
                    lines.append(
                        f"INSERT INTO turns_fts(turn_id,lang,body) VALUES({turn_id},{sql_str(lang)},{sql_str(body)});"
                    )
    for v in extract_vocab(topics):
        lines.append(
            f"INSERT OR IGNORE INTO vocab(lang,term,reading) VALUES({sql_str(v['lang'])},{sql_str(v['term'])},{sql_str(v['reading'])});"
        )
    lines.append("")
    (OUT / "seed.sql").write_text("\n".join(lines) + "\n", encoding="utf-8")

    if cache:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")

    n_turns = sum(len(t["turns"]) for t in topics.values())
    print(f"OK：{len(topics)} 主題、{n_turns} 回合")
    print(f"  {OUT/'schema.sql'} ({(OUT/'schema.sql').stat().st_size} bytes)")
    print(f"  {OUT/'seed.sql'} ({(OUT/'seed.sql').stat().st_size} bytes)")


if __name__ == "__main__":
    main()
