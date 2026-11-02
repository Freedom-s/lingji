"""Lightweight, opt-in timing trace for RAG requests.

The trace deliberately records only timings and aggregate counts.  It never
stores user questions, retrieved text, images, or generated answers.
"""

from __future__ import annotations

import contextvars
import json
import logging
import os
import threading
import time
import uuid
from contextlib import contextmanager
from typing import Any


logger = logging.getLogger("ragflow.performance")
_active_trace: contextvars.ContextVar["PerfTrace | None"] = contextvars.ContextVar(
    "ragflow_perf_trace", default=None
)


def performance_logging_enabled() -> bool:
    return os.getenv("RAGFLOW_PERF_LOG", "0").strip().lower() in {"1", "true", "yes", "on"}


def current_trace():
    return _active_trace.get()


def set_current_trace(trace):
    return _active_trace.set(trace)


def reset_current_trace(token):
    _active_trace.reset(token)


class PerfTrace:
    def __init__(self, operation: str = "rag_request"):
        self.enabled = performance_logging_enabled()
        self.trace_id = uuid.uuid4().hex[:16]
        self.operation = operation
        self.started_ns = time.perf_counter_ns()
        self._events: list[dict[str, Any]] = []
        self._marks: dict[str, int] = {}
        self._meta: dict[str, Any] = {}
        self._lock = threading.Lock()

    def mark(self, name: str) -> None:
        if not self.enabled:
            return
        with self._lock:
            self._marks[name] = time.perf_counter_ns()

    def mark_first(self, name: str) -> None:
        if not self.enabled:
            return
        with self._lock:
            self._marks.setdefault(name, time.perf_counter_ns())

    def set_meta(self, **values: Any) -> None:
        if not self.enabled:
            return
        with self._lock:
            self._meta.update(values)

    def record(self, name: str, duration_ms: float, **meta: Any) -> None:
        if not self.enabled:
            return
        event = {"name": name, "duration_ms": round(float(duration_ms), 3)}
        event.update({k: v for k, v in meta.items() if v is not None})
        with self._lock:
            self._events.append(event)

    @contextmanager
    def span(self, name: str, **meta: Any):
        if not self.enabled:
            yield
            return
        started_ns = time.perf_counter_ns()
        try:
            yield
        finally:
            duration_ms = (time.perf_counter_ns() - started_ns) / 1_000_000
            self.record(name, duration_ms, **meta)

    def finish(self) -> None:
        if not self.enabled:
            return
        finished_ns = time.perf_counter_ns()
        with self._lock:
            marks = dict(self._marks)
            events = list(self._events)
            meta = dict(self._meta)

        mark_ms = {
            name: round((timestamp - self.started_ns) / 1_000_000, 3)
            for name, timestamp in marks.items()
        }
        payload = {
            "trace_id": self.trace_id,
            "operation": self.operation,
            "total_ms": round((finished_ns - self.started_ns) / 1_000_000, 3),
            "marks_ms": mark_ms,
            "meta": meta,
            "events": events,
        }
        logger.info("[RAG_PERF] %s", json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


@contextmanager
def perf_span(name: str, trace=None, **meta: Any):
    trace = trace or current_trace()
    if trace is None:
        yield
        return
    with trace.span(name, **meta):
        yield
