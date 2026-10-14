"""Thông tin máy (CPU, RAM, GPU/VRAM, ổ đĩa) và cài đặt người dùng (~/.micow/settings.json)."""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys

from . import paths


def gpu_info() -> dict:
    info = {"backend": "cpu", "name": "", "vram_gb": 0.0}
    if shutil.which("nvidia-smi"):
        try:
            out = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                                 capture_output=True, text=True, timeout=8).stdout.strip().splitlines()
            if out:
                name, mem = [s.strip() for s in out[0].split(",")[:2]]
                return {"backend": "cuda", "name": name, "vram_gb": round(float(mem) / 1024, 1)}
        except Exception:
            pass
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        info.update(backend="mps", name="Apple Silicon")
        try:
            mem = int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout)
            info["vram_gb"] = round(mem / 2 ** 30 * 0.7, 1)  # bộ nhớ hợp nhất, dùng được ~70%
        except Exception:
            pass
    return info


def ram_gb() -> float:
    try:
        if hasattr(os, "sysconf") and "SC_PHYS_PAGES" in os.sysconf_names:
            return round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2 ** 30, 1)
        if platform.system() == "Windows":
            import ctypes

            class MS(ctypes.Structure):
                _fields_ = [("l", ctypes.c_ulong), ("m", ctypes.c_ulong), ("t", ctypes.c_ulonglong), ("a", ctypes.c_ulonglong),
                            ("tp", ctypes.c_ulonglong), ("ap", ctypes.c_ulonglong), ("tv", ctypes.c_ulonglong),
                            ("av", ctypes.c_ulonglong), ("e", ctypes.c_ulonglong)]
            ms = MS()
            ms.l = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
            return round(ms.t / 2 ** 30, 1)
    except Exception:
        pass
    return 0.0


def torch_available() -> bool:
    try:
        import importlib.util
        return importlib.util.find_spec("torch") is not None
    except Exception:
        return False


def info() -> dict:
    du = shutil.disk_usage(paths.home())
    g = gpu_info()
    rec = "micow-dsp"
    if g["backend"] in ("cuda", "mps") and g["vram_gb"] >= 4:
        rec = "ace-step"
    return {"os": f"{platform.system()} {platform.release()}", "python": sys.version.split()[0],
            "cpu": platform.processor() or platform.machine(), "cores": os.cpu_count(), "ram_gb": ram_gb(),
            "gpu": g, "disk_free_gb": round(du.free / 2 ** 30, 1), "home": str(paths.home()),
            "ffmpeg": shutil.which("ffmpeg") is not None, "git": shutil.which("git") is not None,
            "torch": torch_available(), "recommended_engine": rec}


DEFAULTS = {"acestep": {"url": "http://127.0.0.1:8001", "managed": True, "dit": "acestep-v15-turbo",
                        "lm": "", "api_key": "", "steps": 8},
            "target_lufs": -14.0}


def settings() -> dict:
    p = paths.home() / "settings.json"
    s = json.loads(json.dumps(DEFAULTS))
    if p.exists():
        try:
            user = json.loads(p.read_text(encoding="utf-8"))
            for k, v in user.items():
                if isinstance(v, dict) and isinstance(s.get(k), dict):
                    s[k].update(v)
                else:
                    s[k] = v
        except Exception:
            pass
    return s


def save_settings(patch: dict) -> dict:
    s = settings()
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(s.get(k), dict):
            s[k].update(v)
        else:
            s[k] = v
    (paths.home() / "settings.json").write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
    return s
