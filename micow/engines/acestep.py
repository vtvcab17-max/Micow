"""Engine ACE-Step 1.5 (MIT, ACE Studio × StepFun) – lõi mở gần Suno nhất: bài hát có giọng hát thật.

Micow cài ACE-Step 1.5 vào ~/.micow/engines/ACE-Step-1.5 (git + uv), tải trọng số vào
~/.micow/models/ace-step, rồi chạy REST API của nó ở 127.0.0.1:8001 và điều khiển qua HTTP.
Có thể trỏ sang một máy chủ ACE-Step khác trong mạng LAN (Cài đặt → URL).

Các tác vụ Micow dùng:
  text2music  – lời + phong cách (+ clip "style" làm reference audio)
  cover       – clip "cover": giữ cấu trúc/giai điệu của clip, đổi phong cách / lời
  complete    – clip "complete": thêm nhạc cụ + giọng cho đoạn chưa hoàn chỉnh (cần model base)
  micow+cover – clip "loop/chop/kit": Micow Beat dựng phần đệm theo planner, ACE-Step "cover" lại
                bằng nhạc cụ thật và hát lời (giữ cấu trúc của Micow)
"""
from __future__ import annotations

import json
import mimetypes
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

import numpy as np

from .. import paths, system
from ..audio_io import SR, read_audio, write_wav
from ..dsp import master as mastering
from ..dsp.render import render
from ..lyrics import language_of, parse_lyrics, to_engine_lyrics
from ..outputs import save_result
from .base import Engine, GenRequest, blueprint_for

REPO_URL = "https://github.com/ace-step/ACE-Step-1.5.git"
_PROC: subprocess.Popen | None = None


def repo_dir() -> Path:
    return paths.engines() / "ACE-Step-1.5"


def ckpt_dir() -> Path:
    d = paths.models() / "ace-step"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _uv() -> list[str] | None:
    if shutil.which("uv"):
        return [shutil.which("uv")]
    try:
        subprocess.run([sys.executable, "-m", "uv", "--version"], capture_output=True, check=True)
        return [sys.executable, "-m", "uv"]
    except Exception:
        return None


def _run_stream(cmd: list[str], job, cwd: Path | None = None, env: dict | None = None, p0=0.0, p1=1.0):
    job.update(p0, "$ " + " ".join(str(c) for c in cmd))
    proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace", bufsize=1)
    n = 0
    for line in proc.stdout:  # type: ignore[union-attr]
        line = line.strip()
        if line:
            n += 1
            job.update(min(p1, p0 + (p1 - p0) * (1 - 1 / (1 + n / 60))), line[:240])
        if job.cancel.is_set():
            proc.terminate()
            raise RuntimeError("Đã huỷ")
    if proc.wait() != 0:
        raise RuntimeError(f"Lệnh lỗi (mã {proc.returncode}): {' '.join(map(str, cmd[:3]))}…")


def _multipart(fields: dict, files: dict[str, Path]) -> tuple[bytes, str]:
    b = "----micow" + uuid.uuid4().hex
    out = bytearray()
    for k, v in fields.items():
        if v is None:
            continue
        if isinstance(v, bool):
            v = "true" if v else "false"
        out += f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
    for k, p in files.items():
        ct = mimetypes.guess_type(str(p))[0] or "application/octet-stream"
        out += (f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{p.name}\"\r\n"
                f"Content-Type: {ct}\r\n\r\n").encode()
        out += p.read_bytes() + b"\r\n"
    out += f"--{b}--\r\n".encode()
    return bytes(out), f"multipart/form-data; boundary={b}"


class AceStepEngine(Engine):
    id = "ace-step"
    name = "ACE-Step 1.5"
    license = "MIT – nhạc tạo ra dùng thương mại được (theo model card ACE-Step 1.5)"
    description = ("Mô hình mã nguồn mở gần Suno nhất (LM lập kế hoạch + Diffusion Transformer): hát thật theo lời "
                   "50+ ngôn ngữ có tiếng Việt, cover / làm đầy từ clip, 10 giây – 10 phút. "
                   "Cần GPU ≥ 4 GB VRAM (NVIDIA, AMD ROCm) hoặc Apple Silicon; tải ~10 GB lần đầu.")
    vocals = True

    # ---------- trạng thái ----------
    def cfg(self) -> dict:
        return system.settings()["acestep"]

    def url(self) -> str:
        return self.cfg()["url"].rstrip("/")

    def _api(self, path: str, data: bytes | None = None, ctype: str = "application/json", timeout: float = 30):
        req = urllib.request.Request(self.url() + path, data=data, method="POST" if data is not None else "GET")
        if data is not None:
            req.add_header("Content-Type", ctype)
        key = self.cfg().get("api_key")
        if key:
            req.add_header("Authorization", f"Bearer {key}")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
        return json.loads(raw.decode("utf-8")) if raw[:1] in (b"{", b"[") else raw

    def healthy(self) -> bool:
        try:
            d = self._api("/health", timeout=3)
            return isinstance(d, dict) and (d.get("data") or {}).get("status") == "ok"
        except Exception:
            return False

    def installed(self) -> bool:
        return (repo_dir() / "pyproject.toml").exists() and (repo_dir() / ".venv").exists()

    def status(self) -> dict:
        managed = self.cfg().get("managed", True)
        running = self.healthy()
        inst = self.installed()
        has_ckpt = any(ckpt_dir().glob("*/config.json")) or any(ckpt_dir().glob("*/*.safetensors"))
        if running:
            msg = f"Đang chạy tại {self.url()}"
        elif not managed:
            msg = f"Máy chủ ngoài {self.url()} chưa phản hồi"
        elif not inst:
            msg = "Chưa cài – bấm Cài đặt (cần Git, ~10 GB ổ đĩa, GPU khuyến nghị)"
        else:
            msg = "Đã cài, chưa chạy – Micow sẽ tự khởi động khi tạo nhạc"
        return {"installed": inst or (not managed), "running": running, "ready": running or (inst and managed),
                "weights": has_ckpt, "message": msg, "url": self.url(), "managed": managed}

    # ---------- cài đặt ----------
    def install(self, job) -> dict:
        if not shutil.which("git"):
            raise RuntimeError("Cần cài Git trước (https://git-scm.com/downloads) rồi bấm Cài đặt lại.")
        rd = repo_dir()
        if (rd / ".git").exists():
            _run_stream(["git", "-C", str(rd), "pull", "--ff-only"], job, p0=0.02, p1=0.08)
        else:
            _run_stream(["git", "clone", "--depth", "1", REPO_URL, str(rd)], job, p0=0.02, p1=0.1)
        uv = _uv()
        if uv is None:
            _run_stream([sys.executable, "-m", "pip", "install", "uv"], job, p0=0.1, p1=0.14)
            uv = _uv()
        if uv is None:
            raise RuntimeError("Không cài được uv (trình quản lý gói của ACE-Step).")
        env = dict(os.environ, ACESTEP_CHECKPOINTS_DIR=str(ckpt_dir()))
        _run_stream(uv + ["sync"], job, cwd=rd, env=env, p0=0.15, p1=0.55)
        job.update(0.56, "Tải trọng số mô hình (lần đầu ~10 GB, tuỳ mạng)")
        _run_stream(uv + ["run", "acestep-download"], job, cwd=rd, env=env, p0=0.56, p1=0.9)
        if job.params.get("with_base"):
            _run_stream(uv + ["run", "acestep-download", "--model", "acestep-v15-base", "--skip-main"], job,
                        cwd=rd, env=env, p0=0.9, p1=0.98)
        return {"message": "Đã cài ACE-Step 1.5", "path": str(rd)}

    # ---------- chạy máy chủ ----------
    def start(self, wait: float = 900, job=None) -> None:
        global _PROC
        if self.healthy():
            return
        if not self.cfg().get("managed", True):
            raise RuntimeError(f"Không kết nối được ACE-Step tại {self.url()}")
        if not self.installed():
            raise RuntimeError("ACE-Step 1.5 chưa được cài. Vào mục Mô hình → ACE-Step 1.5 → Cài đặt.")
        uv = _uv()
        if uv is None:
            raise RuntimeError("Thiếu uv để chạy ACE-Step.")
        if _PROC is None or _PROC.poll() is not None:
            u = urllib.parse.urlparse(self.url())
            g = system.gpu_info()
            env = dict(os.environ, ACESTEP_API_HOST=u.hostname or "127.0.0.1", ACESTEP_API_PORT=str(u.port or 8001),
                       ACESTEP_CHECKPOINTS_DIR=str(ckpt_dir()), ACESTEP_CONFIG_PATH=self.cfg().get("dit") or "acestep-v15-turbo")
            if not (sys.platform.startswith("linux") and g["backend"] == "cuda"):
                env.setdefault("ACESTEP_LM_BACKEND", "pt")  # vLLM chỉ có trên Linux + CUDA
            if self.cfg().get("lm"):
                env["ACESTEP_LM_MODEL_PATH"] = self.cfg()["lm"]
            if g["backend"] == "cuda" and g["vram_gb"] < 12:
                env["ACESTEP_OFFLOAD_TO_CPU"] = "true"
            if (ckpt_dir() / "acestep-v15-base").exists():
                env["ACESTEP_CONFIG_PATH2"] = "acestep-v15-base"
            log = open(paths.logs() / "acestep.log", "ab")
            kw = {"start_new_session": True} if os.name != "nt" else {"creationflags": 0x00000200}
            _PROC = subprocess.Popen(uv + ["run", "acestep-api"], cwd=repo_dir(), env=env, stdout=log,
                                     stderr=subprocess.STDOUT, **kw)
        t0 = time.time()
        while time.time() - t0 < wait:
            if self.healthy():
                return
            if _PROC.poll() is not None:
                raise RuntimeError("ACE-Step dừng khi khởi động – xem ~/.micow/logs/acestep.log")
            if job is not None:
                if job.cancel.is_set():
                    raise RuntimeError("Đã huỷ")
                job.update(0.05, f"Đang khởi động ACE-Step 1.5 ({int(time.time() - t0)} giây, lần đầu nạp mô hình lâu)")
            time.sleep(2)
        raise RuntimeError("ACE-Step khởi động quá lâu – xem ~/.micow/logs/acestep.log")

    def stop(self) -> None:
        global _PROC
        if _PROC is not None and _PROC.poll() is None:
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(_PROC.pid)], capture_output=True)
            else:
                try:
                    os.killpg(_PROC.pid, signal.SIGTERM)
                except Exception:
                    _PROC.terminate()
        _PROC = None

    # ---------- sinh nhạc ----------
    def generate(self, job, req: GenRequest, clips: list[dict]) -> dict:
        self.start(job=job)
        bp = blueprint_for(req, clips)
        opts = req.options or {}
        instrumental = req.mode == "beat" or not req.lyrics.strip()
        lyrics = "[Instrumental]" if instrumental else to_engine_lyrics(parse_lyrics(req.lyrics))
        dur = float(req.duration or min(600.0, max(10.0, bp.duration)))
        fields = {"prompt": bp.style.caption(instrumental), "lyrics": lyrics, "bpm": bp.bpm,
                  "key_scale": bp.key.name(), "time_signature": "4", "audio_duration": round(dur, 1),
                  "vocal_language": "unknown" if instrumental else language_of(req.lyrics),
                  "thinking": bool(opts.get("thinking", True)), "batch_size": 1, "audio_format": "wav",
                  "use_random_seed": False, "seed": req.seed,
                  "inference_steps": int(opts.get("steps") or self.cfg().get("steps") or 8),
                  "task_type": "text2music"}
        files: dict[str, Path] = {}
        work = paths.library() / job.id / "_src"
        work.mkdir(parents=True, exist_ok=True)
        by_use = {c["use"]: c for c in reversed(clips)}
        mode_note = "Lời + phong cách"
        if "cover" in by_use:
            fields["task_type"] = "cover"
            fields["audio_cover_strength"] = float(opts.get("cover_strength", 0.6))
            files["src_audio"] = Path(by_use["cover"]["path"])
            fields.pop("audio_duration")
            mode_note = "Cover từ clip"
        elif "complete" in by_use:
            fields["task_type"] = "complete"
            fields["model"] = "acestep-v15-base"
            fields["instruction"] = "Complete the input track with drums, bass, keyboard, guitar" + ("" if instrumental else ", vocals") + ":"
            files["src_audio"] = Path(by_use["complete"]["path"])
            fields.pop("audio_duration")
            mode_note = "Làm đầy từ clip (model base)"
        elif any(u in by_use for u in ("loop", "chop", "kit")):
            job.update(0.08, "Micow Beat dựng phần đệm theo bản thiết kế")
            use_clips = [c for c in clips if c["use"] in ("loop", "chop", "kit")]
            res = render(bp, use_clips, gender=req.gender, guide_vocal=False)
            backing = work / "micow_backing.wav"
            write_wav(backing, res.mix)
            fields["task_type"] = "cover"
            fields["audio_cover_strength"] = float(opts.get("cover_strength", 0.5))
            files["src_audio"] = backing
            fields.pop("audio_duration")
            mode_note = "Micow Beat + ACE-Step cover"
        if "style" in by_use and fields["task_type"] == "text2music":
            files["reference_audio"] = Path(by_use["style"]["path"])
            mode_note += " + clip tham chiếu"
        if opts.get("model"):
            fields["model"] = opts["model"]

        job.update(0.12, f"Gửi tác vụ cho ACE-Step ({mode_note})")
        body, ctype = _multipart(fields, files)
        r = self._api("/release_task", body, ctype, timeout=120)
        task_id = (r.get("data") or {}).get("task_id")
        if not task_id:
            raise RuntimeError(f"ACE-Step không nhận tác vụ: {r}")
        t0 = time.time()
        expect = max(20.0, dur * 0.4)
        while True:
            if job.cancel.is_set():
                raise RuntimeError("Đã huỷ")
            time.sleep(2)
            q = self._api("/query_result", json.dumps({"task_id_list": [task_id]}).encode(), timeout=30)
            item = (q.get("data") or [{}])[0]
            st = item.get("status")
            el = time.time() - t0
            job.update(0.15 + 0.7 * (1 - np.exp(-el / expect)), f"ACE-Step đang tạo… {int(el)} giây")
            if st == 1:
                break
            if st == 2:
                raise RuntimeError(f"ACE-Step báo lỗi: {item.get('result') or item}")
            if el > 3600:
                raise RuntimeError("ACE-Step chạy quá 60 phút")
        results = item.get("result")
        results = json.loads(results) if isinstance(results, str) else results
        first = results[0] if isinstance(results, list) else results
        url = first["file"]
        job.update(0.88, "Tải âm thanh về")
        raw = self._api(url if url.startswith("/") else "/" + url.split("/", 3)[-1], timeout=300)
        out = work / "ace.wav"
        out.write_bytes(raw if isinstance(raw, (bytes, bytearray)) else json.dumps(raw).encode())
        audio = read_audio(out, SR)
        if opts.get("master", True):
            audio, mstats = mastering.master(audio, bp.style.genre, system.settings().get("target_lufs", -14.0))
        else:
            mstats = {}
        metas = first.get("metas") or {}
        meta = {"id": job.id, "title": bp.title, "mode": bp.mode, "engine": self.id, "engine_name": self.name,
                "request": req.to_dict(), "bpm": metas.get("bpm") or bp.bpm, "key": bp.key.to_dict(),
                "genre": bp.style.genre, "genre_name": bp.style.preset["name"], "stats": mstats,
                "notes": bp.notes + [mode_note, f"seed {first.get('seed_value', req.seed)}"],
                "sections": bp.to_dict()["sections"] if fields["task_type"] == "text2music" else [],
                "ace": {"task": fields["task_type"], "dit": first.get("dit_model"), "lm": first.get("lm_model"),
                        "caption": fields["prompt"]}, "created": job.created}
        shutil.rmtree(work, ignore_errors=True)
        return save_result(paths.library() / job.id, meta, audio, None, None, None, bp.to_dict())
