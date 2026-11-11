
# mini-lang
小字集語言，包含『英法中日韓』

## 目錄

- `corpus/`：語料。`corpus/chinese/` 為純中文，`corpus/*.txt` 為中／英／法／日／韓五語平行版
- `spec.md`：迷你語 mini-x 規格與中文字集
- `code/`：檢查與建置腳本
  - `code/charset_check.py`：中文字集檢查
  - `code/parallel_check.py`：多語結構與中文一致性檢查
  - `code/build_site.py`：語料 → D1 schema/seed（含 ruby 拼音資料）
- `cloudflare/`：學習網站（Cloudflare Workers + D1，本機用 rucloud 測試），詳見 `cloudflare/README.md`

## 快速開始（本機跑網站）

```bash
python3 code/build_site.py                     # 重建語料資料庫
rucloud dev cloudflare --d1-init DB=db/schema.sql
rucloud d1 execute cloudflare DB --file cloudflare/db/seed.sql
# 開 http://localhost:8787
```
