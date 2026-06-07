from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from app.services.answer_service import AnswerService
from app.storage.db import init_db


def _contains(text: str, token: str) -> bool:
    return token.casefold() in text.casefold()


def check_answer(case: dict, answer: str) -> list[str]:
    expects = case.get('expects') or {}
    problems: list[str] = []

    for token in expects.get('must_contain_all', []):
        if not _contains(answer, str(token)):
            problems.append(f"missing token: {token}")

    any_groups = expects.get('must_contain_any', [])
    if any_groups and all(not _contains(answer, str(token)) for token in any_groups):
        problems.append(f"missing any of: {', '.join(map(str, any_groups))}")

    for token in expects.get('must_not_contain', []):
        if _contains(answer, str(token)):
            problems.append(f"forbidden token: {token}")

    return problems


def load_cases(path: Path) -> list[dict]:
    cases: list[dict] = []
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        cases.append(json.loads(line))
    return cases


async def run(path: Path) -> int:
    init_db()
    service = AnswerService()
    passed = 0
    cases = load_cases(path)
    for i, case in enumerate(cases, start=1):
        resp = await service.answer(case['query'], answer_style='short')
        answer = resp.get('answer') or ''
        problems = check_answer(case, answer)
        ok = not problems
        passed += int(ok)
        print(f"[{i}] {'PASS' if ok else 'FAIL'} {case.get('id', '')}: {case['query']}")
        if problems:
            for problem in problems:
                print(f"    - {problem}")
            print(f"    answer: {answer}")

    total = len(cases)
    print(f'Passed {passed}/{total}')
    return 0 if passed == total else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--cases',
        default='eval/marketplace_answer_cases.jsonl',
        help='Path to JSONL answer eval cases.',
    )
    args = parser.parse_args()
    return asyncio.run(run(Path(args.cases)))


if __name__ == '__main__':
    raise SystemExit(main())
