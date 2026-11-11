#!/usr/bin/env python3
"""檢查多語 corpus/<topic>.txt 的結構：

1. 每個回合必須有 中/英/法/日/韓 五行，且順序固定。
2. 中文的句子必須與 corpus/chinese/<topic>.txt 完全相同（依序）。
3. 中文行必須全在 spec.md 的中文字集內。

用法：
    python3 code/parallel_check.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "spec.md"
LABELS = ["中", "英", "法", "日", "韓"]
TURN = re.compile(r"^(中|英|法|日|韓) ([AB]): (.*)$")
ZH_LINE = re.compile(r"^中 [AB]: (.*)$")


def allowed_chars(spec_path: Path) -> set:
    spec = spec_path.read_text(encoding="utf-8")
    start = spec.index("## 中文字集")
    end = spec.index("## 日語", start)
    return set(re.findall(r"[\u4e00-\u9fff]", spec[start:end]))


def source_zh(path: Path):
    out = []
    for line in path.read_text(encoding="utf-8").split("\n"):
        if line.startswith("#") or not line.strip():
            continue
        out.append(re.sub(r"^[AB]: ", "", line))
    return out


def check_multi(path: Path, src: Path, allowed: set):
    errors = []
    lines = path.read_text(encoding="utf-8").split("\n")
    turns = []
    for i, line in enumerate(lines, 1):
        if not line.strip() or line.startswith("#"):
            continue
        m = TURN.match(line)
        if not m:
            errors.append(f"line {i}: 格式錯誤 -> {line!r}")
            continue
        turns.append((i, m.group(1), m.group(2), m.group(3)))

    for k in range(0, len(turns) - 4, 5):
        block = turns[k:k + 5]
        labels = [b[1] for b in block]
        if labels != LABELS:
            errors.append(f"line {block[0][0]}: 語言順序應為 {LABELS}，實為 {labels}")
        speakers = {b[2] for b in block}
        if len(speakers) != 1:
            errors.append(f"line {block[0][0]}: 同一回合的說話者不一致 {speakers}")

    zh = [b[3] for b in turns if b[1] == "中"]
    src_lines = source_zh(src)
    if zh != src_lines:
        if len(zh) != len(src_lines):
            errors.append(f"中文行數 {len(zh)} != 來源 {len(src_lines)}")
        for i, (a, b) in enumerate(zip(zh, src_lines), 1):
            if a != b:
                errors.append(f"第 {i} 個中文句不同：\n  多語: {a}\n  來源: {b}")
                break

    for i, label, _, text in turns:
        if label not in ("中", "日"):
            continue
        for ch in text:
            if "\u4e00" <= ch <= "\u9fff" and ch not in allowed:
                errors.append(f"line {i}: {label} 的中文字 '{ch}' 不在中文字集")
                break
    return errors


def main():
    allowed = allowed_chars(SPEC)
    failed = False
    for path in sorted((ROOT / "corpus").glob("*.txt")):
        src = ROOT / "corpus" / "chinese" / path.name
        if not src.exists():
            continue
        errors = check_multi(path, src, allowed)
        if errors:
            failed = True
            print(f"{path.relative_to(ROOT)}: FAIL")
            for e in errors:
                print(f"  {e}")
        else:
            print(f"{path.relative_to(ROOT)}: OK ({path.stat().st_size} bytes)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
