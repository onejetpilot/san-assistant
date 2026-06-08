from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

import httpx

from app.evaluation.run_answer_eval import check_answer, load_cases


def _preview(text: str, limit: int = 300) -> str:
    return ' '.join(str(text or '').split())[:limit]


def _problems_for_response(case: dict[str, Any], response: dict[str, Any]) -> list[str]:
    problems = check_answer(case, response.get('answer') or '')
    if not response.get('answer'):
        problems.append('empty answer')
    if response.get('answer_mode') == 'clarify' and not case.get('allow_clarify'):
        problems.append('unexpected clarification')
    return problems


async def _ask_chat(
    client: httpx.AsyncClient,
    base_url: str,
    query: str,
    token: str = '',
    answer_style: str = 'short',
) -> dict[str, Any]:
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    resp = await client.post(
        f"{base_url.rstrip('/')}/api/chat",
        json={
            'session_id': None,
            'conversation_id': None,
            'message': query,
            'answer_style': answer_style,
        },
        headers=headers,
    )
    resp.raise_for_status()
    return resp.json()


async def run_eval(base_url: str, cases_path: Path, token: str = '', answer_style: str = 'short') -> int:
    cases = load_cases(cases_path)
    passed = 0
    async with httpx.AsyncClient(timeout=60) as client:
        for idx, case in enumerate(cases, start=1):
            try:
                response = await _ask_chat(client, base_url, case['query'], token=token, answer_style=answer_style)
                problems = _problems_for_response(case, response)
            except Exception as exc:
                response = {}
                problems = [f'{type(exc).__name__}: {exc}']

            ok = not problems
            passed += int(ok)
            tools = ','.join(response.get('tools_used') or [])
            sources_count = len(response.get('sources') or [])
            docs_count = len(response.get('documents') or [])
            print(f"[{idx:02d}] {'PASS' if ok else 'FAIL'} {case.get('id', '')} tools={tools} sources={sources_count} docs={docs_count}")
            if problems:
                for problem in problems:
                    print(f"    - {problem}")
                print(f"    q: {_preview(case.get('query', ''))}")
                print(f"    answer: {_preview(response.get('answer', ''))}")

    total = len(cases)
    print(f'Passed {passed}/{total}')
    return 0 if passed == total else 1


def main() -> int:
    parser = argparse.ArgumentParser(description='Run answer eval cases against a live /api/chat endpoint.')
    parser.add_argument('--base-url', default=os.getenv('APP_BASE_URL', ''), help='Backend base URL, e.g. https://example.com')
    parser.add_argument('--token', default=os.getenv('APP_ACCESS_TOKEN', ''), help='Optional API access token.')
    parser.add_argument('--cases', default='eval/marketplace_answer_cases.jsonl')
    parser.add_argument('--answer-style', default='short', choices=['short', 'detailed'])
    args = parser.parse_args()
    if not args.base_url:
        parser.error('--base-url is required or APP_BASE_URL must be set')
    return asyncio.run(run_eval(
        base_url=args.base_url,
        cases_path=Path(args.cases),
        token=args.token,
        answer_style=args.answer_style,
    ))


if __name__ == '__main__':
    raise SystemExit(main())
