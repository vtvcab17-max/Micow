"""Danh sách engine của Micow."""
from __future__ import annotations

from .acestep import AceStepEngine
from .base import Engine, GenRequest, load_clip
from .dsp_engine import DSPEngine
from .micowlm import MicowLMEngine

ENGINES: dict[str, Engine] = {e.id: e for e in (DSPEngine(), AceStepEngine(), MicowLMEngine())}


def get(eid: str) -> Engine:
    if eid not in ENGINES:
        raise KeyError(f"Không có engine '{eid}'")
    return ENGINES[eid]


__all__ = ["ENGINES", "get", "GenRequest", "load_clip", "Engine"]
