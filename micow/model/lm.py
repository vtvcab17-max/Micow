"""Micow-LM – transformer tự hồi quy sinh token âm thanh, kiến trúc suy ra từ những gì Suno công bố.

Chuỗi đầu vào (một transformer chỉ-giải-mã duy nhất, giống Bark/nanoGPT mà Suno kế thừa):

  [<style> phong cách <meta> bpm/giọng/thời điểm <lyrics> lời…]  [<ref> token clip tham chiếu </ref>]  [BOS, khung 1, khung 2, …]
   └──────────── byte UTF-8 (không âm vị) ─────────────┘    └── "dựa trên đoạn nhạc đưa vào" ──┘   └ K sổ mã RVQ / khung ┘

* Mỗi khung âm thanh = tổng embedding của K sổ mã; K đầu ra dự đoán K token của bước kế tiếp.
* "Delay pattern" (MusicGen): sổ mã k trễ k bước → sinh K sổ mã song song mà vẫn tự hồi quy giữa chúng.
* Classifier-free guidance: huấn luyện bỏ điều kiện 10%, khi sinh trộn logit có/không điều kiện.
* Sinh dài: cửa sổ trượt + ép token đã biết (dùng cho cả "nối dài clip" kiểu Suno Extend).
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F

from .tokenizer import SP, VOCAB, empty_text


@dataclass
class LMConfig:
    n_q: int = 8
    card: int = 1024
    dim: int = 512
    layers: int = 8
    heads: int = 8
    mlp_mult: float = 2.75
    max_text: int = 2048
    max_ref: int = 500          # 10 giây ở 50 Hz
    max_audio: int = 1500       # cửa sổ 30 giây ở 50 Hz
    dropout: float = 0.0
    cond_drop: float = 0.1
    ref_drop: float = 0.5
    rope_base: float = 10000.0
    frame_rate: float = 50.0
    sample_rate: int = 32000

    @classmethod
    def preset(cls, name: str, **kw) -> "LMConfig":
        p = {"tiny": dict(dim=64, layers=2, heads=2, max_audio=200, max_ref=50, max_text=256),
             "small": dict(dim=512, layers=8, heads=8),
             "base": dict(dim=1024, layers=24, heads=16, max_audio=3000),
             "large": dict(dim=1536, layers=32, heads=24, max_audio=4500)}[name]
        p.update(kw)
        return cls(**p)

    def to_dict(self) -> dict:
        return asdict(self)


class RMSNorm(nn.Module):
    def __init__(self, d: int):
        super().__init__()
        self.w = nn.Parameter(torch.ones(d))

    def forward(self, x):
        return x * torch.rsqrt(x.pow(2).mean(-1, keepdim=True) + 1e-6) * self.w


def rope(x, pos, base):
    """x (B, H, L, Dh), pos (B, L)"""
    dh = x.shape[-1]
    inv = 1.0 / (base ** (torch.arange(0, dh, 2, device=x.device, dtype=torch.float32) / dh))
    ang = pos.float()[..., None] * inv  # (B, L, dh/2)
    cos, sin = ang.cos()[:, None].to(x.dtype), ang.sin()[:, None].to(x.dtype)
    x1, x2 = x[..., ::2], x[..., 1::2]
    return torch.stack([x1 * cos - x2 * sin, x1 * sin + x2 * cos], -1).flatten(-2)


class Block(nn.Module):
    def __init__(self, c: LMConfig):
        super().__init__()
        self.c = c
        self.n1, self.n2 = RMSNorm(c.dim), RMSNorm(c.dim)
        self.qkv = nn.Linear(c.dim, 3 * c.dim, bias=False)
        self.proj = nn.Linear(c.dim, c.dim, bias=False)
        h = int(c.mlp_mult * c.dim)
        self.w12 = nn.Linear(c.dim, 2 * h, bias=False)
        self.w3 = nn.Linear(h, c.dim, bias=False)
        self.drop = nn.Dropout(c.dropout)

    def forward(self, x, pos, mask, cache=None):
        B, L, D = x.shape
        H = self.c.heads
        q, k, v = self.qkv(self.n1(x)).view(B, L, 3, H, D // H).permute(2, 0, 3, 1, 4)
        q, k = rope(q, pos, self.c.rope_base), rope(k, pos, self.c.rope_base)
        if cache is not None:
            if cache.get("k") is not None:
                k = torch.cat([cache["k"], k], 2)
                v = torch.cat([cache["v"], v], 2)
            cache["k"], cache["v"] = k, v
        a = F.scaled_dot_product_attention(q, k, v, attn_mask=mask,
                                           dropout_p=self.c.dropout if self.training else 0.0)
        x = x + self.drop(self.proj(a.transpose(1, 2).reshape(B, L, D)))
        g, u = self.w12(self.n2(x)).chunk(2, -1)
        return x + self.drop(self.w3(F.silu(g) * u))


def delay(codes: torch.Tensor, pad: int) -> torch.Tensor:
    """(B, K, T) → (B, K, T+K-1): sổ mã k trễ k bước."""
    B, K, T = codes.shape
    out = codes.new_full((B, K, T + K - 1), pad)
    for k in range(K):
        out[:, k, k:k + T] = codes[:, k]
    return out


def undelay(d: torch.Tensor, T: int) -> torch.Tensor:
    B, K, S = d.shape
    return torch.stack([d[:, k, k:k + T] for k in range(K)], 1)


class MicowLM(nn.Module):
    def __init__(self, c: LMConfig):
        super().__init__()
        self.c = c
        self.PAD, self.BOS = c.card, c.card + 1
        self.text_emb = nn.Embedding(VOCAB, c.dim)
        self.code_emb = nn.ModuleList([nn.Embedding(c.card + 2, c.dim) for _ in range(c.n_q)])
        self.type_emb = nn.Embedding(3, c.dim)  # 0 text, 1 ref, 2 audio
        self.blocks = nn.ModuleList([Block(c) for _ in range(c.layers)])
        self.norm = RMSNorm(c.dim)
        self.heads = nn.ModuleList([nn.Linear(c.dim, c.card, bias=False) for _ in range(c.n_q)])
        self.apply(self._init)

    @staticmethod
    def _init(m):
        if isinstance(m, (nn.Linear, nn.Embedding)):
            nn.init.normal_(m.weight, std=0.02)

    def n_params(self) -> int:
        return sum(p.numel() for p in self.parameters())

    def embed_frames(self, codes: torch.Tensor, typ: int) -> torch.Tensor:
        """codes (B, K, L) → (B, L, D)"""
        e = sum(self.code_emb[k](codes[:, k]) for k in range(codes.shape[1]))
        return e + self.type_emb.weight[typ]

    # ---------- dựng tiền tố (văn bản + clip tham chiếu) ----------
    def prefix(self, texts: list[list[int]], refs: list[torch.Tensor | None], device) -> tuple[torch.Tensor, torch.Tensor]:
        """Trả embedding tiền tố đã căn trái (left-pad) và mặt nạ hợp lệ (B, P)."""
        parts, valid = [], []
        for t, r in zip(texts, refs):
            te = self.text_emb(torch.tensor(t[: self.c.max_text], device=device)) + self.type_emb.weight[0]
            seq = [te]
            if r is not None and r.numel():
                r = r[:, : self.c.max_ref].to(device)
                mk = self.text_emb(torch.tensor([SP["<ref>"], SP["</ref>"]], device=device)) + self.type_emb.weight[0]
                seq += [mk[:1], self.embed_frames(r[None], 1)[0], mk[1:]]
            e = torch.cat(seq, 0)
            parts.append(e)
        P = max(p.shape[0] for p in parts)
        out = torch.zeros(len(parts), P, self.c.dim, device=device, dtype=parts[0].dtype)
        mask = torch.zeros(len(parts), P, dtype=torch.bool, device=device)
        for i, p in enumerate(parts):
            out[i, P - p.shape[0]:] = p
            mask[i, P - p.shape[0]:] = True
        return out, mask

    def _run(self, x, valid, caches=None, start_pos=None):
        """x (B, L, D); valid (B, Ltotal) gồm cả phần đã cache; trả hidden (B, L, D)."""
        B, L, _ = x.shape
        Lt = valid.shape[1]
        pos_all = (valid.long().cumsum(1) - 1).clamp(min=0)
        pos = pos_all[:, Lt - L:]
        causal = torch.ones(L, Lt, dtype=torch.bool, device=x.device).tril(Lt - L)
        mask = (causal[None] & valid[:, None, :])[:, None]
        # hàng chỉ toàn pad (vị trí pad bên trái) → cho tự nhìn chính nó để tránh NaN
        diag = torch.zeros(L, Lt, dtype=torch.bool, device=x.device)
        diag[torch.arange(L), Lt - L + torch.arange(L)] = True
        mask = mask | diag[None, None]
        for i, b in enumerate(self.blocks):
            x = b(x, pos, mask, None if caches is None else caches[i])
        return self.norm(x)

    # ---------- huấn luyện ----------
    def forward(self, texts: list[list[int]], codes: torch.Tensor, refs: list[torch.Tensor | None] | None = None):
        """codes (B, K, T) – trả loss trung bình qua K sổ mã (và loss từng sổ mã)."""
        dev = codes.device
        B, K, T = codes.shape
        if self.training:
            texts = [empty_text() if torch.rand(()) < self.c.cond_drop else t for t in texts]
            refs = [None if (r is None or torch.rand(()) < self.c.ref_drop) else r for r in (refs or [None] * B)]
        refs = refs or [None] * B
        pre, pmask = self.prefix(texts, refs, dev)
        d = delay(codes, self.PAD)                                         # (B, K, S)
        inp = torch.cat([torch.full((B, K, 1), self.BOS, device=dev, dtype=d.dtype), d[:, :, :-1]], 2)
        x = torch.cat([pre, self.embed_frames(inp, 2)], 1)
        valid = torch.cat([pmask, torch.ones(B, inp.shape[2], dtype=torch.bool, device=dev)], 1)
        h = self._run(x, valid)[:, pre.shape[1]:]
        losses = []
        for k in range(K):
            logits = self.heads[k](h)
            tgt = d[:, k].clone()
            tgt[tgt == self.PAD] = -100
            losses.append(F.cross_entropy(logits.reshape(-1, self.c.card).float(), tgt.reshape(-1), ignore_index=-100))
        loss = torch.stack(losses).mean()
        return loss, [l.item() for l in losses]

    # ---------- sinh ----------
    @torch.no_grad()
    def generate(self, text: list[int], n_frames: int, ref: torch.Tensor | None = None,
                 prompt: torch.Tensor | None = None, cfg_scale: float = 3.0, temperature: float = 1.0,
                 top_k: int = 250, top_p: float = 0.0, text_fn=None, progress=None, generator=None) -> torch.Tensor:
        """Sinh (K, n_frames) token. prompt (K, Tp): khung đã biết ở đầu (nối dài clip).
        text_fn(start_frame) → token văn bản cho từng cửa sổ (để báo thời điểm trong bài)."""
        dev = next(self.parameters()).device
        K = self.c.n_q
        codes = torch.full((K, n_frames), -1, dtype=torch.long, device=dev)
        if prompt is not None and prompt.numel():
            tp = min(n_frames, prompt.shape[1])
            codes[:, :tp] = prompt[:, :tp].to(dev)
        W = self.c.max_audio
        ctx = W // 2
        start = 0
        use_cfg = cfg_scale and cfg_scale != 1.0
        while True:
            win_end = min(n_frames, start + W)
            T = win_end - start
            S = T + K - 1
            # token trễ của cửa sổ: -1 = chưa biết, PAD = ngoài phạm vi
            d = torch.full((K, S), self.PAD, dtype=torch.long, device=dev)
            for k in range(K):
                d[k, k:k + T] = codes[k, start:win_end]
            unknown = (d == -1).any(0)
            s0 = int(unknown.nonzero()[0]) if unknown.any() else S
            if s0 < S:
                txt = text_fn(start) if text_fn else text
                texts = [txt, empty_text()] if use_cfg else [txt]
                refs = [ref, None] if use_cfg else [ref]
                pre, pmask = self.prefix(texts, refs, dev)
                Bn = pre.shape[0]
                caches = [dict() for _ in self.blocks]
                inp = torch.cat([torch.full((K, 1), self.BOS, dtype=torch.long, device=dev), d[:, :s0]], 1)
                x = torch.cat([pre, self.embed_frames(inp[None].expand(Bn, K, inp.shape[1]), 2)], 1)
                valid = torch.cat([pmask, torch.ones(Bn, inp.shape[1], dtype=torch.bool, device=dev)], 1)
                h = self._run(x, valid, caches)[:, -1]
                for s in range(s0, S):
                    nxt = d[:, s].clone()
                    for k in range(K):
                        if nxt[k] != -1:
                            continue
                        lg = self.heads[k](h).float()
                        l = lg[1] + cfg_scale * (lg[0] - lg[1]) if use_cfg else lg[0]
                        nxt[k] = _sample(l, temperature, top_k, top_p, generator)
                        codes[k, start + s - k] = nxt[k]
                    d[:, s] = nxt
                    if progress and s % 25 == 0:
                        progress(min(1.0, (start + max(0, s - K)) / n_frames))
                    if s == S - 1:
                        break
                    x = self.embed_frames(nxt.view(1, K, 1).expand(Bn, K, 1), 2)
                    valid = torch.cat([valid, torch.ones(Bn, 1, dtype=torch.bool, device=dev)], 1)
                    h = self._run(x, valid, caches)[:, -1]
            if win_end >= n_frames:
                break
            start = win_end - ctx
        return codes


def _sample(logits, temperature, top_k, top_p, generator):
    if temperature <= 0:
        return logits.argmax()
    logits = logits / temperature
    if top_k and top_k < logits.shape[-1]:
        v, _ = torch.topk(logits, top_k)
        logits = logits.masked_fill(logits < v[-1], float("-inf"))
    probs = F.softmax(logits, -1)
    if top_p and 0 < top_p < 1:
        sp, si = probs.sort(descending=True)
        keep = sp.cumsum(-1) - sp <= top_p
        sp = sp * keep
        probs = torch.zeros_like(probs).scatter(0, si, sp)
        probs = probs / probs.sum()
    return torch.multinomial(probs, 1, generator=generator)[0]


def save_lm(model: MicowLM, path, extra: dict | None = None) -> None:
    torch.save({"config": model.c.to_dict(), "state": model.state_dict(), "kind": "micow-lm", **(extra or {})}, path)


def load_lm(path, device="cpu") -> tuple[MicowLM, dict]:
    ck = torch.load(path, map_location=device, weights_only=False)
    m = MicowLM(LMConfig(**ck["config"]))
    m.load_state_dict(ck["state"])
    return m.to(device).eval(), ck
