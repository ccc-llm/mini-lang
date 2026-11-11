#!/usr/bin/env python3
"""用訓練好的 mini-lang 模型生成對話。

用法：
    python3 llm/generate.py                         # 從「中 A:」開始生成
    python3 llm/generate.py --prompt "中 A: 幾點了？" --tokens 500
    python3 llm/generate.py --lang 韓 --temp 0.9    # 換起始語言標籤
"""
import argparse
import sys
from pathlib import Path

import torch
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).resolve().parent))
from train import MODEL_PATH, MiniGPT, sample  # noqa: E402


def main(argv):
    ap = argparse.ArgumentParser(description="用 mini-lang 模型生成文字")
    ap.add_argument("--prompt", default=None, help="起始文字（預設依 --lang 決定）")
    ap.add_argument("--lang", default="中", choices=["中", "英", "法", "日", "韓"])
    ap.add_argument("--tokens", type=int, default=400)
    ap.add_argument("--temp", type=float, default=0.8)
    ap.add_argument("--topk", type=int, default=40)
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args(argv[1:])

    if not MODEL_PATH.exists():
        print(f"找不到 {MODEL_PATH}，請先執行 python3 llm/train.py")
        return 1
    ckpt = torch.load(MODEL_PATH, map_location="cpu", weights_only=False)
    cfg, itos = ckpt["config"], ckpt["itos"]
    stoi = {c: i for i, c in enumerate(itos)}
    model = MiniGPT(**{k: v for k, v in cfg.items() if k != "batch_size"})
    model.load_state_dict(ckpt["state_dict"])
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    model.to(device)

    if args.seed is not None:
        torch.manual_seed(args.seed)
    prompt = args.prompt if args.prompt is not None else f"{args.lang} A: "
    out = sample(model, itos, stoi, prompt, n=args.tokens,
                 temperature=args.temp, top_k=args.topk, device=device)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
