"""Đọc / ghi âm thanh. WAV dùng numpy thuần; định dạng khác (mp3, m4a, flac…) đi qua ffmpeg nếu có."""
from __future__ import annotations

import io
import shutil
import subprocess
import wave
from pathlib import Path

import numpy as np

SR = 44100  # tần số lấy mẫu nội bộ của Micow


def have_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def _decode_wav_bytes(data: bytes) -> tuple[np.ndarray, int]:
    """Đọc WAV PCM 8/16/24/32-bit hoặc float32 → mảng (n, ch) float32."""
    bio = io.BytesIO(data)
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError("Không phải tệp WAV")
    # Tự đọc chunk để hỗ trợ cả WAVE_FORMAT_IEEE_FLOAT (module wave không đọc được)
    pos, fmt, raw = 12, None, None
    while pos + 8 <= len(data):
        cid, size = data[pos:pos + 4], int.from_bytes(data[pos + 4:pos + 8], "little")
        body = data[pos + 8:pos + 8 + size]
        if cid == b"fmt ":
            tag = int.from_bytes(body[0:2], "little")
            ch = int.from_bytes(body[2:4], "little")
            sr = int.from_bytes(body[4:8], "little")
            bits = int.from_bytes(body[14:16], "little")
            if tag == 0xFFFE and len(body) >= 26:  # WAVE_FORMAT_EXTENSIBLE
                tag = int.from_bytes(body[24:26], "little")
            fmt = (tag, ch, sr, bits)
        elif cid == b"data":
            raw = body
        pos += 8 + size + (size & 1)
    if fmt is None or raw is None:
        bio.close()
        raise ValueError("WAV thiếu fmt/data")
    tag, ch, sr, bits = fmt
    if tag == 3 and bits == 32:
        x = np.frombuffer(raw[: len(raw) // 4 * 4], dtype="<f4").astype(np.float32)
    elif tag == 3 and bits == 64:
        x = np.frombuffer(raw[: len(raw) // 8 * 8], dtype="<f8").astype(np.float32)
    elif bits == 16:
        x = np.frombuffer(raw[: len(raw) // 2 * 2], dtype="<i2").astype(np.float32) / 32768.0
    elif bits == 24:
        b = np.frombuffer(raw[: len(raw) // 3 * 3], dtype=np.uint8).reshape(-1, 3)
        v = (b[:, 0].astype(np.int32) | (b[:, 1].astype(np.int32) << 8) | (b[:, 2].astype(np.int32) << 16))
        v = np.where(v >= 1 << 23, v - (1 << 24), v)
        x = v.astype(np.float32) / float(1 << 23)
    elif bits == 32:
        x = np.frombuffer(raw[: len(raw) // 4 * 4], dtype="<i4").astype(np.float32) / 2147483648.0
    elif bits == 8:
        x = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    else:
        raise ValueError(f"WAV {bits}-bit chưa hỗ trợ")
    n = len(x) // ch
    return x[: n * ch].reshape(n, ch), sr


def read_audio(path: str | Path, sr: int = SR, mono: bool = False) -> np.ndarray:
    """Đọc tệp âm thanh, trả về float32 (n, 2) (hoặc (n,) nếu mono) ở tần số `sr`."""
    path = Path(path)
    data = path.read_bytes()
    try:
        x, file_sr = _decode_wav_bytes(data)
    except ValueError:
        if not have_ffmpeg():
            raise RuntimeError(f"Cần ffmpeg để đọc {path.suffix} (hoặc chuyển sang WAV). Tệp: {path.name}")
        out = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-acodec", "pcm_f32le",
             "-ac", "2", "-ar", str(sr), "-"],
            capture_output=True, check=True)
        x = np.frombuffer(out.stdout, dtype="<f4").reshape(-1, 2).astype(np.float32)
        file_sr = sr
    if x.shape[1] == 1:
        x = np.repeat(x, 2, axis=1)
    elif x.shape[1] > 2:
        x = x[:, :2]
    if file_sr != sr:
        x = resample(x, file_sr, sr)
    return x.mean(axis=1) if mono else x


def resample(x: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    if sr_in == sr_out:
        return x
    from math import gcd
    from scipy.signal import resample_poly
    g = gcd(int(sr_in), int(sr_out))
    return resample_poly(x, sr_out // g, sr_in // g, axis=0).astype(np.float32)


def to_stereo(x: np.ndarray) -> np.ndarray:
    return np.stack([x, x], axis=1) if x.ndim == 1 else x


def write_wav(path: str | Path, x: np.ndarray, sr: int = SR, bits: int = 16) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    x = to_stereo(np.asarray(x, dtype=np.float32))
    x = np.clip(np.nan_to_num(x), -1.0, 1.0)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(x.shape[1])
        w.setframerate(int(sr))
        if bits == 24:
            w.setsampwidth(3)
            v = np.round(x * 8388607.0).astype(np.int32).reshape(-1)
            b = np.stack([(v & 0xFF), (v >> 8) & 0xFF, (v >> 16) & 0xFF], axis=1).astype(np.uint8)
            w.writeframes(b.tobytes())
        else:
            w.setsampwidth(2)
            w.writeframes(np.round(x * 32767.0).astype("<i2").tobytes())
    return path


def write_mp3(path: str | Path, wav_path: str | Path, kbps: int = 256) -> Path | None:
    """Chuyển WAV sang MP3 bằng ffmpeg; trả None nếu máy không có ffmpeg."""
    if not have_ffmpeg():
        return None
    path = Path(path)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wav_path), "-codec:a", "libmp3lame",
                    "-b:a", f"{kbps}k", str(path)], check=True)
    return path


def db(x: float) -> float:
    return 20.0 * np.log10(max(float(x), 1e-12))


def undb(d: float) -> float:
    return float(10.0 ** (d / 20.0))
