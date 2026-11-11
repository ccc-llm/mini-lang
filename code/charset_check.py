#!/usr/bin/env python3
"""檢查語料中的中文是否都在 spec.md 的中文字集內。

- corpus/chinese/*.txt：整個檔案都是中文，逐行檢查。
- corpus/*.txt（多語版）：只檢查以「中 A:」「中 B:」開頭的中文行。

用法：
    python3 code/charset_check.py            # 檢查 corpus/ 下所有 txt
    python3 code/charset_check.py 檔案...     # 只檢查指定檔案
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "spec.md"
ZH_LINE = re.compile(r"^中\s+[AB]:")


def allowed_chars(spec_path: Path) -> set:
    """只取 spec.md「## 中文字集」段落裡的字，不含說明文字。"""
    spec = spec_path.read_text(encoding="utf-8")
    start = spec.index("## 中文字集")
    end = spec.index("## 日語", start)
    return set(re.findall(r"[\u4e00-\u9fff]", spec[start:end]))


def check_file(path: Path, allowed: set) -> dict:
    only_zh = path.parent.name == "chinese"
    bad = {}
    for i, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
        if line.startswith("#"):
            continue
        if not only_zh and not ZH_LINE.match(line):
            continue
        for ch in line:
            if "\u4e00" <= ch <= "\u9fff" and ch not in allowed:
                bad.setdefault(ch, []).append(i)
    return bad


def main(argv):
    files = [Path(a) for a in argv[1:]] or sorted((ROOT / "corpus").rglob("*.txt"))
    files = [f for f in files if f.is_file()]
    allowed = allowed_chars(SPEC)
    failed = False
    for f in files:
        bad = check_file(f, allowed)
        size = f.stat().st_size
        rel = f.relative_to(ROOT)
        if bad:
            failed = True
            print(f"{rel}: {size} bytes  FAIL")
            for ch, lines in sorted(bad.items()):
                print(f"  {ch}: lines {lines}")
        else:
            print(f"{rel}: {size} bytes  OK")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
