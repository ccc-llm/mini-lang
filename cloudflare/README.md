# mini-lang 網站（Cloudflare Workers）

用五語平行語料（中／英／法／日／韓）做的小字集語言學習網站。
資料放在 D1（SQLite），全文檢索用 FTS5。

```
cloudflare/
  wrangler.jsonc   # Workers 設定（assets + D1 binding）
  src/worker.js    # API：lesson / search / vocab / quiz / progress / stats
  public/          # 前端（index.html、app.js、style.css，無 build 步驟）
  db/schema.sql    # D1 schema（含 turns_fts 虛擬表）
  db/seed.sql      # 由 ../code/build_site.py 產生（勿手改）
```

## 功能

- 書架：15 個主題的迷你對話，每句五語對照
- 閱讀：語言顯示開關、**中／日／韓 ruby 拼音標注**（漢語拼音／日文羅馬音／韓文 RR 羅馬拼音）、遮罩回想、點句朗讀（Web Speech API）、標星
- 全文檢索：FTS5，跨五語；中文／日文逐字索引（phrase 查詢），英／法／韓詞級索引（prefix 查詢，法文自動去變音符）
- 詞表：各語言的小詞彙集（中文逐字拼音、日韓逐詞羅馬拼音）
- 測驗：由平行句自動出題（選出對應翻譯），成績存 D1
- 進度：匿名 device id（localStorage）＋ D1，記錄標星與測驗正確率

## 本機測試（rucloud，不部署）

```bash
# 1) 重建語料（corpus/ 有改動時）
python3 code/build_site.py

# 2) 啟動（會自動執行 db/schema.sql，含 FTS5 虛擬表）
rucloud dev cloudflare --d1-init DB=db/schema.sql

# 3) 灌語料（只需一次；改 seed 後重跑）
rucloud d1 execute cloudflare DB --file cloudflare/db/seed.sql

# 4) 驗證
open http://localhost:8787
curl 'localhost:8787/api/search?q=生日&lang=zh'
```

## 部署到 Cloudflare（已部署）

- 線上網址：<https://mini-lang-web.ccckmit.workers.dev>
- D1：`mini-lang-db`（id `7f768cf9-a03a-48d3-9895-e6ac9e7f003a`，APAC）

重新部署流程：

```bash
python3 code/build_site.py                                      # 語料有改時重建 seed
wrangler d1 execute mini-lang-db --remote --file db/schema.sql -y
wrangler d1 execute mini-lang-db --remote --file db/seed.sql -y
wrangler deploy   # 在 cloudflare/ 目錄下
```

注意：含 FTS5 虛擬表的 D1 在匯出（`wrangler d1 export`）時會連 shadow tables 一起倒出，
備份建議只匯 `topics`、`turns`、`vocab`、`progress`、`quiz_log` 五張表（seed.sql 可隨時重建 FTS 索引）。

## ruby 拼音資料

由 `code/build_site.py` 在 build 期產生，存進 `turns.ruby` JSON 欄位：

- 中文：逐字漢語拼音（pypinyin，快取在 `code/data/pinyin_cache.json`）
- 日文：逐詞 Hepburn 羅馬音（假名內建表；含漢字詞用人工讀音表）
- 韓文：逐詞 Revised Romanization（Hangul 音節分解演算法）
