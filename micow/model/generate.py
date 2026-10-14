"""Chạy Micow-LM đã huấn luyện: văn bản (+ clip tham chiếu / clip nối dài) → token → codec → sóng âm."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import torch

from .codec import load_codec
from .lm import load_lm
from .tokenizer import encode_text, meta_string
from .train import pick_device


class MicowLMRunner:
    def __init__(self, model_dir: str | Path, device: str = "auto"):
        self.dir = Path(model_dir)
        self.device = pick_device(device)
        self.lm, ck = load_lm(self.dir / "lm.pt", self.device)
        codec_path = self.dir / "codec.pt"
        if not codec_path.exists() and ck.get("codec"):
            codec_path = Path(ck["codec"])
        self.codec = load_codec(codec_path, self.device)
        self.sr = self.codec.sample_rate
        self.fr = self.codec.frame_rate

    def encode(self, mono: np.ndarray, max_seconds: float | None = None) -> torch.Tensor:
        if max_seconds:
            mono = mono[: int(max_seconds * self.sr)]
        x = torch.from_numpy(np.ascontiguousarray(mono, dtype=np.float32))[None, None].to(self.device)
        return self.codec.encode(x)[0]

    @torch.no_grad()
    def generate(self, style: str, lyrics: str = "", bpm: int | None = None, key: str | None = None,
                 duration: float = 30.0, ref: np.ndarray | None = None, prompt: np.ndarray | None = None,
                 cfg_scale: float = 3.0, temperature: float = 1.0, top_k: int = 250, seed: int = 0,
                 progress=None) -> np.ndarray:
        g = torch.Generator(device="cpu").manual_seed(int(seed))
        torch.manual_seed(int(seed))
        n_frames = int(duration * self.fr)
        ref_codes = self.encode(ref, self.lm.c.max_ref / self.fr) if ref is not None else None
        prompt_codes = self.encode(prompt) if prompt is not None else None

        def text_fn(start_frame: int) -> list[int]:
            return encode_text(style, lyrics, meta_string(bpm, key, duration, start_frame / self.fr), self.lm.c.max_text)

        gen = g if self.device == "cpu" else None
        codes = self.lm.generate(text_fn(0), n_frames, ref=ref_codes, prompt=prompt_codes, cfg_scale=cfg_scale,
                                 temperature=temperature, top_k=top_k, text_fn=text_fn, progress=progress, generator=gen)
        wav = self.codec.decode(codes[None].clamp(min=0))[0, 0].float().cpu().numpy()
        return wav[: int(duration * self.sr)]
