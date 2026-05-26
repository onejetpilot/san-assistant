import asyncio
from pathlib import Path
import yaml

from app.services.answer_service import AnswerService


async def run() -> int:
    data = yaml.safe_load(Path('eval/questions.yml').read_text(encoding='utf-8')) or {}
    questions = data.get('questions', [])
    svc = AnswerService()
    passed = 0
    for i, q in enumerate(questions, start=1):
        resp = await svc.answer(q['question'], session_id=None, answer_style='short')
        answer = (resp.get('answer') or '').lower()
        ok = True
        for token in q.get('expected_contains', []):
            if token.lower() not in answer:
                ok = False
        for token in q.get('forbidden_contains', []):
            if token.lower() in answer:
                ok = False
        if q.get('expected_article'):
            ok = ok and q['expected_article'].upper() in answer.upper()
        if q.get('expected_documents'):
            ok = ok and bool(resp.get('documents'))
        print(f"[{i}] {'PASS' if ok else 'FAIL'}: {q['question']}")
        passed += int(ok)
    total = len(questions)
    print(f'Passed {passed}/{total}')
    return 0 if passed == total else 1


if __name__ == '__main__':
    raise SystemExit(asyncio.run(run()))
