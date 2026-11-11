#!/usr/bin/env python3
"""在 mini-lang 語料上訓練小型 char-level Transformer。

訓練資料：corpus/**/*.txt（原始語料）+ llm/corpus/gen/*.txt（合成語料）。
模型與字表存到 llm/model/model.pt。

用法：
    python3 llm/train.py                    # 預設 3000 步，MPS/CPU 自動選擇
    python3 llm/train.py --steps 6000 --embd 256
    python3 llm/train.py --no-orig          # 只用合成語料
"""
import argparse
import math
import random
import sys
import time
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parent
MODEL_PATH = ROOT / "model" / "model.pt"


# ---------------------------------------------------------------- 資料

def load_text(include_orig=True):
    parts = []
    if include_orig:
        parts += sorted((ROOT.parent / "corpus").rglob("*.txt"))
    parts += sorted((ROOT / "corpus" / "gen").glob("*.txt"))
    texts = []
    for p in parts:
        t = p.read_text(encoding="utf-8")
        if t.strip():
            texts.append(t.strip())
    return "\n\n\n".join(texts)


# ---------------------------------------------------------------- 模型

class Block(nn.Module):
    def __init__(self, n_embd, n_head, block_size, dropout):
        super().__init__()
        self.ln1 = nn.LayerNorm(n_embd)
        self.attn = nn.MultiheadAttention(n_embd, n_head, dropout=dropout, batch_first=True)
        self.ln2 = nn.LayerNorm(n_embd)
        self.mlp = nn.Sequential(
            nn.Linear(n_embd, 4 * n_embd), nn.GELU(),
            nn.Dropout(dropout), nn.Linear(4 * n_embd, n_embd), nn.Dropout(dropout),
        )
        mask = torch.triu(torch.ones(block_size, block_size), 1).bool()
        self.register_buffer("mask", mask)

    def forward(self, x):
        h = self.ln1(x)
        a, _ = self.attn(h, h, h, attn_mask=self.mask[: x.size(1), : x.size(1)], need_weights=False)
        x = x + a
        return x + self.mlp(self.ln2(x))


class MiniGPT(nn.Module):
    def __init__(self, vocab_size, n_embd=192, n_head=4, n_layer=4, block_size=256, dropout=0.1):
        super().__init__()
        self.block_size = block_size
        self.tok = nn.Embedding(vocab_size, n_embd)
        self.pos = nn.Embedding(block_size, n_embd)
        self.drop = nn.Dropout(dropout)
        self.blocks = nn.ModuleList(Block(n_embd, n_head, block_size, dropout) for _ in range(n_layer))
        self.ln = nn.LayerNorm(n_embd)
        self.head = nn.Linear(n_embd, vocab_size, bias=False)
        self.head.weight = self.tok.weight  # weight tying
        self.apply(self._init)

    @staticmethod
    def _init(m):
        if isinstance(m, (nn.Linear, nn.Embedding)):
            nn.init.normal_(m.weight, mean=0.0, std=0.02)
            if isinstance(m, nn.Linear) and m.bias is not None:
                nn.init.zeros_(m.bias)

    def forward(self, idx, targets=None):
        x = self.drop(self.tok(idx) + self.pos(torch.arange(idx.size(1), device=idx.device)))
        for b in self.blocks:
            x = b(x)
        logits = self.head(self.ln(x))
        loss = None
        if targets is not None:
            loss = F.cross_entropy(logits.view(-1, logits.size(-1)), targets.view(-1))
        return logits, loss


# ---------------------------------------------------------------- 訓練

def get_batch(data, block_size, batch_size, device):
    ix = torch.randint(len(data) - block_size - 1, (batch_size,))
    x = torch.stack([data[i: i + block_size] for i in ix])
    y = torch.stack([data[i + 1: i + 1 + block_size] for i in ix])
    return x.to(device), y.to(device)


@torch.no_grad()
def estimate_loss(model, data, cfg, device):
    model.eval()
    losses = []
    for _ in range(20):
        xb, yb = get_batch(data, cfg["block_size"], cfg["batch_size"], device)
        _, loss = model(xb, yb)
        losses.append(loss.item())
    model.train()
    return sum(losses) / len(losses)


@torch.no_grad()
def sample(model, itos, stoi, prompt, n=200, temperature=0.8, top_k=40, device="cpu"):
    model.eval()
    idx = torch.tensor([[stoi.get(c, 0) for c in prompt]], dtype=torch.long, device=device)
    for _ in range(n):
        ctx = idx[:, -model.block_size:]
        logits, _ = model(ctx)
        logits = logits[:, -1, :] / temperature
        if top_k:
            v, _ = torch.topk(logits, min(top_k, logits.size(-1)))
            logits[logits < v[:, [-1]]] = -float("inf")
        probs = F.softmax(logits, dim=-1)
        nxt = torch.multinomial(probs, 1)
        idx = torch.cat([idx, nxt], dim=1)
    return "".join(itos[i] for i in idx[0].tolist())


def main(argv):
    ap = argparse.ArgumentParser(description="訓練 mini-lang 小型語言模型")
    ap.add_argument("--steps", type=int, default=3000)
    ap.add_argument("--n-embd", type=int, default=192)
    ap.add_argument("--n-head", type=int, default=4)
    ap.add_argument("--n-layer", type=int, default=4)
    ap.add_argument("--block-size", type=int, default=256)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--dropout", type=float, default=0.1)
    ap.add_argument("--no-orig", action="store_true", help="不使用 corpus/ 原始語料")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args(argv[1:])

    torch.manual_seed(args.seed)
    random.seed(args.seed)
    device = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")

    text = load_text(include_orig=not args.no_orig)
    chars = sorted(set(text))
    stoi = {c: i for i, c in enumerate(chars)}
    itos = chars
    data = torch.tensor([stoi[c] for c in text], dtype=torch.long)
    print(f"語料 {len(text):,} 字元，字表 {len(chars)}，裝置 {device}")

    cfg = {
        "vocab_size": len(chars), "n_embd": args.n_embd, "n_head": args.n_head,
        "n_layer": args.n_layer, "block_size": args.block_size,
        "dropout": args.dropout, "batch_size": args.batch_size,
    }
    model = MiniGPT(**{k: v for k, v in cfg.items() if k != "batch_size"}).to(device)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"模型參數量：{n_params:,}")

    opt = torch.optim.AdamW(model.parameters(), lr=args.lr)
    sched = torch.optim.lr_scheduler.OneCycleLR(
        opt, max_lr=args.lr, total_steps=args.steps, pct_start=0.05)

    model.train()
    t0 = time.time()
    for step in range(1, args.steps + 1):
        xb, yb = get_batch(data, args.block_size, args.batch_size, device)
        _, loss = model(xb, yb)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        sched.step()
        if step % 200 == 0 or step == 1:
            vl = estimate_loss(model, data, cfg, device)
            print(f"step {step:5d}  loss {loss.item():.3f}  val {vl:.3f}  {time.time()-t0:.0f}s")

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"config": cfg, "itos": itos, "state_dict": model.state_dict()}, MODEL_PATH)
    print(f"已存 {MODEL_PATH.relative_to(ROOT.parent)}")

    demo = sample(model, itos, stoi, "中 A:", n=300, device=device)
    print("--- 隨機樣本 ---")
    print(demo)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
