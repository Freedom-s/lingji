#!/usr/bin/env python3
"""Measure the live RAG HTTP path without retaining test conversations."""

from __future__ import annotations

import argparse
import json
import logging
import os
import statistics
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests


QUESTIONS = [
    "给定代码 int x = 10; int* const ptr = &x，哪些操作是合法的？",
    "C++ 面向对象程序设计中，虚函数和纯虚函数有什么区别？",
    "请解释 C++ 中继承、封装和多态三种面向对象特征。",
    "C++ 类的构造函数和析构函数分别在什么时机被调用？",
    "请说明 C++ 中指针、引用以及 const 修饰之间的主要区别。",
]


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    rank = (len(values) - 1) * p
    low = int(rank)
    high = min(low + 1, len(values) - 1)
    return values[low] + (values[high] - values[low]) * (rank - low)


def summary(values: list[float]) -> dict[str, float | None]:
    return {
        "avg_ms": round(statistics.mean(values), 3) if values else None,
        "p50_ms": round(percentile(values, 0.50), 3) if values else None,
        "p95_ms": round(percentile(values, 0.95), 3) if values else None,
        "p99_ms": round(percentile(values, 0.99), 3) if values else None,
    }


def read_perf_lines(log_path: Path, offset: int) -> list[dict]:
    time.sleep(1.0)
    with log_path.open("rb") as handle:
        handle.seek(offset)
        text = handle.read().decode("utf-8", errors="replace")
    traces = []
    for line in text.splitlines():
        marker = "[RAG_PERF] "
        if marker not in line:
            continue
        payload = line.split(marker, 1)[1].strip()
        try:
            traces.append(json.loads(payload))
        except json.JSONDecodeError:
            continue
    return traces


def create_test_conversations(dialog_id: str, count: int):
    from api.db.db_models import Conversation, User, UserTenant
    from api.db.services.dialog_service import DialogService

    exists, dialog = DialogService.get_by_id(dialog_id)
    if not exists:
        raise RuntimeError(f"dialog not found: {dialog_id}")

    user = (
        User.select(User)
        .join(UserTenant, on=(UserTenant.user_id == User.id))
        .where(
            (UserTenant.tenant_id == dialog.tenant_id)
            & (UserTenant.status == "1")
            & (User.status == "1")
        )
        .first()
    )
    if not user:
        raise RuntimeError("no active user is associated with the dialog tenant")

    token = user.get_id()
    conversations = []
    prologue = dialog.prompt_config.get("prologue", "")
    for _ in range(count):
        conversation_id = uuid.uuid4().hex
        Conversation.create(
            id=conversation_id,
            dialog_id=dialog_id,
            name="performance-test",
            message=[{"id": uuid.uuid4().hex, "role": "assistant", "content": prologue}],
            reference=[],
            user_id=user.id,
        )
        conversations.append((conversation_id, token))
    return conversations


def delete_test_conversations(conversation_ids: list[str]) -> None:
    from api.db.db_models import Conversation

    if conversation_ids:
        Conversation.delete().where(Conversation.id.in_(conversation_ids)).execute()


def request_once(base_url: str, conversation_id: str, token: str, question: str) -> dict:
    url = f"{base_url.rstrip('/')}/v1/conversation/completion"
    payload = {
        "conversation_id": conversation_id,
        "messages": [{"role": "user", "content": question}],
        "quote": False,
    }
    started = time.perf_counter()
    first_event_ms = None
    event_count = 0
    received_bytes = 0
    status = None
    error = None
    app_error = None
    try:
        with requests.post(
            url,
            headers={"Authorization": token, "Content-Type": "application/json"},
            json=payload,
            stream=True,
            timeout=(10, 1200),
        ) as response:
            status = response.status_code
            if status != 200:
                error = f"HTTP {status}"
            for line in response.iter_lines(decode_unicode=False):
                if line:
                    received_bytes += len(line)
                    event_count += 1
                    if b'"code":500' in line or b'"code":401' in line:
                        app_error = "application error response"
                    if first_event_ms is None:
                        first_event_ms = (time.perf_counter() - started) * 1000
            if app_error:
                error = app_error
    except Exception as exc:  # keep the batch running to measure error rate
        error = f"{type(exc).__name__}: {exc}"
    total_ms = (time.perf_counter() - started) * 1000
    return {
        "status": status,
        "ok": status == 200 and error is None,
        "ttft_ms": first_event_ms,
        "total_ms": total_ms,
        "events": event_count,
        "bytes": received_bytes,
        "error": error,
    }


def run_batch(base_url: str, dialog_id: str, concurrency: int, count: int, warmup: bool = False):
    conversations = create_test_conversations(dialog_id, count)
    ids = [item[0] for item in conversations]
    try:
        if warmup:
            request_once(base_url, conversations[0][0], conversations[0][1], QUESTIONS[0])
            return []
        results = []
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [
                executor.submit(
                    request_once,
                    base_url,
                    conversation_id,
                    token,
                    QUESTIONS[index % len(QUESTIONS)],
                )
                for index, (conversation_id, token) in enumerate(conversations)
            ]
            for future in as_completed(futures):
                results.append(future.result())
        return results
    finally:
        delete_test_conversations(ids)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dialog-id", required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:9380")
    parser.add_argument("--requests-per-level", type=int, default=5)
    parser.add_argument("--levels", default="1,2,5")
    parser.add_argument("--log-file", default="")
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()

    os.environ["RAGFLOW_PERF_LOG"] = "1"
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    from api import settings

    settings.init_settings()
    log_path = Path(args.log_file) if args.log_file else max(Path("api/logs").glob("start_*.log"), key=lambda p: p.stat().st_mtime)
    log_offset = log_path.stat().st_size

    run_batch(args.base_url, args.dialog_id, 1, 1, warmup=True)
    log_offset = log_path.stat().st_size

    all_results = {}
    for concurrency in [int(value) for value in args.levels.split(",") if value.strip()]:
        started = time.perf_counter()
        results = run_batch(args.base_url, args.dialog_id, concurrency, args.requests_per_level)
        elapsed_ms = (time.perf_counter() - started) * 1000
        all_results[str(concurrency)] = {
            "concurrency": concurrency,
            "count": len(results),
            "success_count": sum(1 for result in results if result["ok"]),
            "elapsed_ms": round(elapsed_ms, 3),
            "qps": round(len(results) / (elapsed_ms / 1000), 5) if elapsed_ms else None,
            "ttft": summary([result["ttft_ms"] for result in results if result["ttft_ms"] is not None]),
            "total": summary([result["total_ms"] for result in results]),
            "raw": results,
        }

    traces = read_perf_lines(log_path, log_offset)
    stage_values: dict[str, list[float]] = {}
    for trace in traces:
        for event in trace.get("events", []):
            stage_values.setdefault(event["name"], []).append(event["duration_ms"])

    output = {
        "base_url": args.base_url,
        "dialog_id": args.dialog_id,
        "requests_per_level": args.requests_per_level,
        "results": all_results,
        "stage_summary": {name: summary(values) for name, values in sorted(stage_values.items())},
        "trace_count": len(traces),
        "trace_log": str(log_path),
    }
    if args.summary_only:
        for level in output["results"].values():
            level.pop("raw", None)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if all(item["success_count"] == item["count"] for item in all_results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
