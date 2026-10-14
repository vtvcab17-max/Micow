"""Hàng đợi công việc chạy nền (tạo nhạc, cài engine). Một luồng sinh nhạc để không tranh GPU/CPU."""
from __future__ import annotations

import json
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from . import paths


@dataclass
class Job:
    id: str
    kind: str                 # generate | install | train
    params: dict
    status: str = "queued"    # queued | running | done | error | cancelled
    progress: float = 0.0
    message: str = "Đang chờ"
    result: dict | None = None
    error: str | None = None
    created: float = field(default_factory=time.time)
    log: list[str] = field(default_factory=list)
    cancel: threading.Event = field(default_factory=threading.Event)

    def update(self, progress: float | None = None, message: str | None = None):
        if progress is not None:
            self.progress = max(0.0, min(1.0, float(progress)))
        if message:
            self.message = message
            self.log.append(f"{time.strftime('%H:%M:%S')} {message}")
            del self.log[:-300]

    def to_dict(self) -> dict:
        return {"id": self.id, "kind": self.kind, "status": self.status, "progress": round(self.progress, 3),
                "message": self.message, "result": self.result, "error": self.error, "created": self.created,
                "params": {k: v for k, v in self.params.items() if k not in ("lyrics",)}, "log": self.log[-40:]}


class JobQueue:
    def __init__(self):
        self.jobs: dict[str, Job] = {}
        self.gen_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="micow-gen")
        self.aux_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="micow-aux")
        self.lock = threading.Lock()

    def submit(self, kind: str, params: dict, fn) -> Job:
        job = Job(id=time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6], kind=kind, params=params)
        with self.lock:
            self.jobs[job.id] = job
            # giữ tối đa 200 job trong bộ nhớ
            if len(self.jobs) > 200:
                for k in sorted(self.jobs, key=lambda k: self.jobs[k].created)[:-200]:
                    self.jobs.pop(k, None)
        pool = self.gen_pool if kind in ("generate", "train", "listen") else self.aux_pool

        def run():
            if job.cancel.is_set():
                job.status = "cancelled"
                return
            job.status = "running"
            job.update(0.01, "Bắt đầu")
            try:
                job.result = fn(job)
                job.status = "done"
                job.update(1.0, "Hoàn tất")
            except Exception as e:  # noqa: BLE001 – báo lỗi cho người dùng thay vì làm sập máy chủ
                job.status = "cancelled" if job.cancel.is_set() else "error"
                job.error = str(e) or e.__class__.__name__
                job.update(None, "Lỗi: " + job.error)
                (paths.logs() / f"{job.id}.log").write_text(
                    json.dumps(job.to_dict(), ensure_ascii=False, indent=1) + "\n" + traceback.format_exc(), encoding="utf-8")
        pool.submit(run)
        return job

    def get(self, jid: str) -> Job | None:
        return self.jobs.get(jid)

    def list(self) -> list[dict]:
        return [j.to_dict() for j in sorted(self.jobs.values(), key=lambda j: -j.created)]


QUEUE = JobQueue()
