# corpus

迷你語 mini-x 語料。

- `chinese/`：純中文對話（每個主題一檔）。
- 根目錄 `*.txt`：多語對照版（中／英／法／日／韓），中文行與 `chinese/<topic>.txt` 相同。
- `VOCAB.md`：各語言共用的小詞彙集。
- `MULTILINGUAL.md`：多語對話的格式規格。

## 檢查

    python3 code/charset_check.py    # 中文字集檢查
    python3 code/parallel_check.py   # 多語結構與中英對應檢查
