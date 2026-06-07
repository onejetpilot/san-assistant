from __future__ import annotations

from typing import Any


def build_tool_payload(
    query: str,
    results: list[dict[str, Any]] | None = None,
    note: str = '',
    meta: dict[str, Any] | None = None,
    status: str = 'ok',
    error: str = '',
    mode: str = '',
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        'status': status,
        'query': query,
        'count': len(results or []),
        'results': results or [],
        'note': note,
        'error': error,
        'meta': meta or {},
    }
    if mode:
        payload['mode'] = mode
    return payload


def empty_results_payload(
    query: str,
    note: str = '',
    meta: dict[str, Any] | None = None,
    mode: str = '',
) -> dict[str, Any]:
    return build_tool_payload(query, note=note, meta=meta, status='empty', mode=mode)


def error_payload(
    query: str,
    error: str,
    note: str = '',
    meta: dict[str, Any] | None = None,
    mode: str = '',
) -> dict[str, Any]:
    return build_tool_payload(query, note=note, meta=meta, status='error', error=error, mode=mode)
