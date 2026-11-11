# 多語對話格式（mini-x multi-corpus）

`corpus/<topic>.txt` 是多語對話檔。每個中文句子都配有 English / Français / 日本語 / 한국어 的對應句。

## 格式

一個對話回合（turn）由 5 行組成，順序固定：

```
中 A: 今天是我生日。
英 A: Today is my birthday.
法 A: Aujourd'hui, c'est mon anniversaire.
日 A: きょうは たんじょうびだ。
韓 A: 오늘은 내 생일이다.

中 B: 真的？生日快樂。
英 B: Really? Happy birthday.
法 B: Vraiment ? Joyeux anniversaire.
日 B: ほんとう？たんじょうびおめでとう。
韓 B: 그래요? 생일 축하해요.
```

- 前綴固定為 `中` `英` `法` `日` `韓`，後面接 ` A:` 或 ` B:`。
- 中文行（`中 A:` / `中 B:`）必須與 `corpus/chinese/<topic>.txt` 的對應句子完全相同，不可改寫。
- 每個回合之間空一行。
- 檔開頭可以放 `#` 註解說明（例如語言標籤對應）。

## 字集規則

1. 數字一律用阿拉伯數字 0-9。
2. 小字集寫不出來的詞，直接用 English 寫（例：medicine、umbrella、market、computer）。
3. 中文、日文詞彙盡量少；英文、法文、韓文同樣遵守小詞彙集。
4. 中文用字必須在 `spec.md` 的「## 中文字集」內。
5. 日文盡量用五十音（ひらがな／カタカナ），用漢字只能用中文字集裡的字。
6. 韓文只用 한글，不用漢字。
7. 法文可用 é è à ç ù 等字母。

共用小詞彙集見 `corpus/VOCAB.md`。

## 檢查

```
python3 code/charset_check.py
```

會驗證中文行是否全在中文字集內。
