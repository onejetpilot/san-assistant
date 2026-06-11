import json
from pathlib import Path


EVAL_CASES = Path('eval/marketplace_answer_cases.jsonl')


def _load_cases() -> list[dict]:
    return [json.loads(line) for line in EVAL_CASES.read_text(encoding='utf-8').splitlines() if line.strip()]


def test_marketplace_answer_cases_are_valid_jsonl():
    cases = _load_cases()
    assert cases
    assert all(case.get('id') and case.get('query') and case.get('expects') for case in cases)
