-- mini-lang D1 schema（SQLite / FTS5）
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
