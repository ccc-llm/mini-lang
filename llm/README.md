# llm：mini-lang 小型語言模型

用神經網路學習 mini-x 語料，生成中／英／法／日／韓五語平行對話。

## 目錄

- `generate_corpus.py`：語料擴增腳本。以「回合模板 + 詞槽」組合出五語平行對話，中文行會對照 `spec.md` 中文字集檢查（日文漢字、韓文漢字不符只警告）
- `train.py`：訓練腳本。char-level 小型 Transformer（預設約 2M 參數），資料為 `corpus/` 原始語料 + `corpus/gen/` 合成語料
- `generate.py`：推理腳本。載入 `model/model.pt` 生成對話
- `corpus/gen/`：合成語料輸出位置（`gen_<主題>.txt`，格式與 `corpus/MULTILINGUAL.md` 相同，不會動到原始 `corpus/`）
- `model/`：模型權重輸出位置（`model.pt` 內含模型設定、字表、參數）

## 快速開始

```bash
python3 llm/generate_corpus.py              # 生成合成語料（預設 10 主題 × 300 篇）
python3 llm/train.py                        # 訓練（預設 3000 步，MPS/CPU 自動選擇）
python3 llm/generate.py                     # 從「中 A:」開始生成
```

## 常用參數

```bash
# 語料
python3 llm/generate_corpus.py --theme weather --per-file 500 --seed 42

# 訓練
python3 llm/train.py --steps 6000 --n-embd 256 --n-layer 4   # 更大模型
python3 llm/train.py --no-orig                                # 只用合成語料

# 生成
python3 llm/generate.py --lang 韓 --tokens 200 --temp 0.9
python3 llm/generate.py --prompt "中 A: 幾點了？" --tokens 250 --seed 7
```

## 驗證合成語料

```bash
python3 code/charset_check.py "$(pwd)"/llm/corpus/gen/*.txt
```

`generate_corpus.py` 本身也會在產生前檢查模板用字，中文字集違規會列出錯誤並中止。

## 已知限制

- 模型小、語料為模板組合，生成品質是「合理的 mini-x 風格」，不是真正的新文章
- 五語之間的數字偶爾會不一致（各語言行條件獨立取樣），可用較低 `--temp` 或更多訓練步數改善
