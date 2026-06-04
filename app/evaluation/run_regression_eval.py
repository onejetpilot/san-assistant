import asyncio
from pathlib import Path
import yaml

from app.services.answer_service import AnswerService
from app.storage.db import init_db


def _contains(text: str, token: str) -> bool:
    return token.casefold() in text.casefold()


def _check_question(q: dict, resp: dict) -> tuple[bool, list[str]]:
    answer = resp.get('answer') or ''
    problems: list[str] = []

    for token in q.get('expected_contains', []):
        if not _contains(answer, str(token)):
            problems.append(f"missing answer token: {token}")

    for token in q.get('forbidden_contains', []):
        if _contains(answer, str(token)):
            problems.append(f"forbidden answer token: {token}")

    if q.get('expected_article') and not _contains(answer, str(q['expected_article'])):
        problems.append(f"missing expected article: {q['expected_article']}")

    if q.get('expected_documents') is not None:
        has_documents = bool(resp.get('documents'))
        if has_documents != bool(q['expected_documents']):
            problems.append(f"documents expected={q['expected_documents']} actual={has_documents}")

    if q.get('expected_answer_mode') and resp.get('answer_mode') != q['expected_answer_mode']:
        problems.append(f"answer_mode expected={q['expected_answer_mode']} actual={resp.get('answer_mode')}")

    if q.get('expected_confidence') and resp.get('confidence') != q['expected_confidence']:
        problems.append(f"confidence expected={q['expected_confidence']} actual={resp.get('confidence')}")

    return not problems, problems


async def run() -> int:
    init_db()
    data = yaml.safe_load(Path('eval/questions.yml').read_text(encoding='utf-8')) or {}
    questions = data.get('questions', [])
    svc = AnswerService()
    passed = 0
    for i, q in enumerate(questions, start=1):
        resp = await svc.answer(q['question'], session_id=None, answer_style='short')
        ok, problems = _check_question(q, resp)
        print(f"[{i}] {'PASS' if ok else 'FAIL'}: {q['question']}")
        if problems:
            for problem in problems:
                print(f"    - {problem}")
            print(f"    answer: {resp.get('answer')}")
        passed += int(ok)
    total = len(questions)
    print(f'Passed {passed}/{total}')
    return 0 if passed == total else 1


if __name__ == '__main__':
    raise SystemExit(asyncio.run(run()))
