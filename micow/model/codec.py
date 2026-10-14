"""Micow Codec – bộ mã hoá âm thanh thần kinh (kiểu SoundStream/EnCodec) biến sóng âm thành token rời rạc.

  sóng âm 32 kHz ──Encoder (conv, stride 2·4·8·10 = 640)──▶ latent 50 Hz ──RVQ (n_q sổ mã)──▶ token [n_q, T]
  token ──tra sổ mã──▶ latent ──Decoder (conv chuyển vị)──▶ sóng âm

"Tokenize âm thanh đúng cách" là phần Suno nói họ đầu tư nhiều nhất; đây là bản mở tương đương.
Huấn luyện: L1 sóng + STFT đa phân giải + commitment (+ tuỳ chọn discriminator MS-STFT).
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

import torch
import torch.nn as nn
import torch.nn.functional as F


@dataclass
class CodecConfig:
    sample_rate: int = 32000
    channels: int = 32
    strides: list[int] = field(default_factory=lambda: [2, 4, 8, 10])
    dim: int = 128
    n_q: int = 8
    codebook_size: int = 1024
    ema_decay: float = 0.99

    @property
    def hop(self) -> int:
        return int(math.prod(self.strides))

    @property
    def frame_rate(self) -> float:
        return self.sample_rate / self.hop

    @classmethod
    def tiny(cls) -> "CodecConfig":
        return cls(sample_rate=16000, channels=8, strides=[2, 4, 5, 8], dim=32, n_q=4, codebook_size=64)

    def to_dict(self) -> dict:
        return asdict(self)


def _wn(m: nn.Module) -> nn.Module:
    return nn.utils.parametrizations.weight_norm(m)


class ResUnit(nn.Module):
    def __init__(self, ch: int, dil: int):
        super().__init__()
        self.c1 = _wn(nn.Conv1d(ch, ch, 7, dilation=dil, padding=3 * dil))
        self.c2 = _wn(nn.Conv1d(ch, ch, 1))

    def forward(self, x):
        return x + self.c2(F.elu(self.c1(F.elu(x))))


class EncBlock(nn.Module):
    def __init__(self, cin: int, cout: int, stride: int):
        super().__init__()
        self.res = nn.Sequential(ResUnit(cin, 1), ResUnit(cin, 3), ResUnit(cin, 9))
        self.down = _wn(nn.Conv1d(cin, cout, 2 * stride, stride=stride, padding=math.ceil(stride / 2)))

    def forward(self, x):
        return self.down(F.elu(self.res(x)))


class DecBlock(nn.Module):
    def __init__(self, cin: int, cout: int, stride: int):
        super().__init__()
        self.up = _wn(nn.ConvTranspose1d(cin, cout, 2 * stride, stride=stride, padding=math.ceil(stride / 2),
                                         output_padding=stride % 2))
        self.res = nn.Sequential(ResUnit(cout, 1), ResUnit(cout, 3), ResUnit(cout, 9))

    def forward(self, x):
        return self.res(self.up(F.elu(x)))


class VectorQuantizer(nn.Module):
    """Sổ mã cập nhật bằng EMA, khởi tạo lại mã chết bằng vector ngẫu nhiên trong batch."""

    def __init__(self, dim: int, size: int, decay: float):
        super().__init__()
        self.decay = decay
        self.register_buffer("embed", torch.randn(size, dim) * 0.1)
        self.register_buffer("cluster_size", torch.ones(size))
        self.register_buffer("embed_avg", self.embed.clone())

    def encode(self, x):  # x (B, T, D) → idx (B, T)
        flat = x.reshape(-1, x.shape[-1])
        d = flat.pow(2).sum(1, keepdim=True) - 2 * flat @ self.embed.t() + self.embed.pow(2).sum(1)[None]
        return d.argmin(1).view(x.shape[:-1])

    def decode(self, idx):
        return F.embedding(idx, self.embed)

    def forward(self, x):
        idx = self.encode(x)
        q = self.decode(idx)
        if self.training:
            with torch.no_grad():
                flat = x.reshape(-1, x.shape[-1]).float()
                onehot = F.one_hot(idx.view(-1), self.embed.shape[0]).float()
                self.cluster_size.mul_(self.decay).add_(onehot.sum(0), alpha=1 - self.decay)
                self.embed_avg.mul_(self.decay).add_(onehot.t() @ flat, alpha=1 - self.decay)
                n = self.cluster_size.sum()
                cs = (self.cluster_size + 1e-5) / (n + self.embed.shape[0] * 1e-5) * n
                self.embed.copy_(self.embed_avg / cs[:, None])
                dead = self.cluster_size < 0.02
                if dead.any():
                    rnd = flat[torch.randint(0, flat.shape[0], (int(dead.sum()),), device=flat.device)]
                    self.embed[dead] = rnd.to(self.embed.dtype)
                    self.embed_avg[dead] = rnd.to(self.embed.dtype)
                    self.cluster_size[dead] = 1.0
        commit = F.mse_loss(x, q.detach())
        q = x + (q - x).detach()  # straight-through
        return q, idx, commit


class RVQ(nn.Module):
    def __init__(self, cfg: CodecConfig):
        super().__init__()
        self.layers = nn.ModuleList([VectorQuantizer(cfg.dim, cfg.codebook_size, cfg.ema_decay) for _ in range(cfg.n_q)])

    def forward(self, z, n_q: int | None = None):  # z (B, T, D)
        n_q = n_q or len(self.layers)
        res, out, codes, loss = z, torch.zeros_like(z), [], z.new_zeros(())
        for layer in self.layers[:n_q]:
            q, idx, c = layer(res)
            res = res - q
            out = out + q
            codes.append(idx)
            loss = loss + c
        return out, torch.stack(codes, 1), loss  # codes (B, n_q, T)

    def decode(self, codes):  # (B, n_q, T)
        return sum(self.layers[i].decode(codes[:, i]) for i in range(codes.shape[1]))


class MicowCodec(nn.Module):
    def __init__(self, cfg: CodecConfig | None = None):
        super().__init__()
        self.cfg = cfg = cfg or CodecConfig()
        ch = cfg.channels
        enc = [_wn(nn.Conv1d(1, ch, 7, padding=3))]
        c = ch
        for s in cfg.strides:
            enc.append(EncBlock(c, c * 2, s))
            c *= 2
        enc += [nn.ELU(), _wn(nn.Conv1d(c, cfg.dim, 3, padding=1))]
        self.encoder = nn.Sequential(*enc)
        dec = [_wn(nn.Conv1d(cfg.dim, c, 7, padding=3))]
        for s in reversed(cfg.strides):
            dec.append(DecBlock(c, c // 2, s))
            c //= 2
        dec += [nn.ELU(), _wn(nn.Conv1d(c, 1, 7, padding=3)), nn.Tanh()]
        self.decoder = nn.Sequential(*dec)
        self.quantizer = RVQ(cfg)

    def _pad(self, wav):
        hop = self.cfg.hop
        T = wav.shape[-1]
        p = (hop - T % hop) % hop
        return F.pad(wav, (0, p)), T

    def forward(self, wav, n_q: int | None = None):  # wav (B, 1, T)
        wav, T = self._pad(wav)
        z = self.encoder(wav).transpose(1, 2)
        q, codes, commit = self.quantizer(z, n_q)
        y = self.decoder(q.transpose(1, 2))[..., :T]
        return y, codes, commit

    @torch.no_grad()
    def encode(self, wav) -> torch.Tensor:
        wav, _ = self._pad(wav)
        z = self.encoder(wav).transpose(1, 2)
        return self.quantizer(z)[1]

    @torch.no_grad()
    def decode(self, codes) -> torch.Tensor:
        return self.decoder(self.quantizer.decode(codes).transpose(1, 2))

    @property
    def n_q(self) -> int:
        return self.cfg.n_q

    @property
    def codebook_size(self) -> int:
        return self.cfg.codebook_size

    @property
    def sample_rate(self) -> int:
        return self.cfg.sample_rate

    @property
    def frame_rate(self) -> float:
        return self.cfg.frame_rate


# ---------------- loss ----------------
def stft_loss(y, x, scales=(2048, 1024, 512, 256, 128)) -> torch.Tensor:
    loss = y.new_zeros(())
    y, x = y.squeeze(1), x.squeeze(1)
    for n in scales:
        if x.shape[-1] < n:
            continue
        w = torch.hann_window(n, device=x.device)
        Y = torch.stft(y, n, n // 4, window=w, return_complex=True).abs()
        X = torch.stft(x, n, n // 4, window=w, return_complex=True).abs()
        loss = loss + (Y - X).abs().mean() + (torch.log(Y + 1e-5) - torch.log(X + 1e-5)).abs().mean()
    return loss


class STFTDiscriminator(nn.Module):
    """Discriminator trên phổ STFT đa phân giải (giống EnCodec, rút gọn)."""

    def __init__(self, scales=(2048, 1024, 512), ch: int = 32):
        super().__init__()
        self.scales = scales
        self.nets = nn.ModuleList()
        for _ in scales:
            self.nets.append(nn.ModuleList([
                _wn(nn.Conv2d(2, ch, (3, 9), padding=(1, 4))),
                _wn(nn.Conv2d(ch, ch, (3, 9), stride=(1, 2), padding=(1, 4))),
                _wn(nn.Conv2d(ch, ch, (3, 9), stride=(1, 2), padding=(1, 4))),
                _wn(nn.Conv2d(ch, ch, (3, 3), padding=(1, 1))),
                _wn(nn.Conv2d(ch, 1, (3, 3), padding=(1, 1)))]))

    def forward(self, x):
        outs, feats = [], []
        x = x.squeeze(1)
        for n, net in zip(self.scales, self.nets):
            w = torch.hann_window(n, device=x.device)
            S = torch.stft(x, n, n // 4, window=w, return_complex=True)
            h = torch.stack([S.real, S.imag], 1).transpose(2, 3)
            fs = []
            for i, layer in enumerate(net):
                h = layer(h)
                if i < len(net) - 1:
                    h = F.leaky_relu(h, 0.2)
                    fs.append(h)
            outs.append(h)
            feats.append(fs)
        return outs, feats


def save_codec(model: MicowCodec, path) -> None:
    torch.save({"config": model.cfg.to_dict(), "state": model.state_dict(), "kind": "micow-codec"}, path)


def load_codec(path, device="cpu") -> MicowCodec:
    ck = torch.load(path, map_location=device, weights_only=False)
    m = MicowCodec(CodecConfig(**ck["config"]))
    m.load_state_dict(ck["state"])
    return m.to(device).eval()
