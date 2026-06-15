from __future__ import annotations

import logging
import threading
import time
from contextlib import contextmanager
from typing import Any, Generator

logger = logging.getLogger(__name__)

_RESULTS: dict[str, list[dict[str, Any]]] = {}
_RESULTS_LOCK = threading.Lock()


def _get_results_list(name: str) -> list[dict[str, Any]]:
    with _RESULTS_LOCK:
        if name not in _RESULTS:
            _RESULTS[name] = []
        return _RESULTS[name]


@contextmanager
def route_timer(name: str) -> Generator[None, None, None]:
    start = time.perf_counter()
    results = _get_results_list(name)
    entry = {"name": name, "elapsed_ms": None, "steps": []}
    results.append(entry)
    if len(results) > 100:
        results.pop(0)
    try:
        yield
    finally:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        entry["elapsed_ms"] = elapsed_ms


@contextmanager
def step_timer(timer_name: str, step_name: str) -> Generator[None, None, None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        results = _get_results_list(timer_name)
        if results and results[-1]["name"] == timer_name:
            results[-1]["steps"].append({"step": step_name, "elapsed_ms": elapsed_ms})


def collect_timing(name: str, elapsed_ms: float, step: str | None = None) -> None:
    results = _get_results_list(name)
    if step:
        if results and results[-1]["name"] == name:
            results[-1]["steps"].append({"step": step, "elapsed_ms": elapsed_ms})
    else:
        results.append({"name": name, "elapsed_ms": elapsed_ms, "steps": []})
        if len(results) > 100:
            results.pop(0)


def get_timing(name: str | None = None) -> list[dict[str, Any]]:
    if name:
        return list(_get_results_list(name))
    with _RESULTS_LOCK:
        return [{"name": k, "records": list(v)} for k, v in _RESULTS.items()]


def clear_timing(name: str | None = None) -> None:
    with _RESULTS_LOCK:
        if name:
            _RESULTS.pop(name, None)
        else:
            _RESULTS.clear()


def diagnosis_record(
    issue: str,
    expected: str,
    observed: str,
    environment: str,
    api_evidence: str | None = None,
    backend_timing: str | None = None,
    cache_evidence: str | None = None,
    websocket_evidence: str | None = None,
    infra_evidence: str | None = None,
    broker_evidence: str | None = None,
    root_cause: str | None = None,
    chosen_fix: str | None = None,
) -> dict[str, str | None]:
    return {
        "issue": issue,
        "expected": expected,
        "observed": observed,
        "environment": environment,
        "api_evidence": api_evidence,
        "backend_timing": backend_timing,
        "cache_evidence": cache_evidence,
        "websocket_evidence": websocket_evidence,
        "infra_evidence": infra_evidence,
        "broker_evidence": broker_evidence,
        "root_cause": root_cause,
        "chosen_fix": chosen_fix,
    }
