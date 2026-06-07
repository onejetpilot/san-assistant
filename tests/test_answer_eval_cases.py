import json
from pathlib import Path

from app.evaluation.run_answer_eval import check_answer
from app.rag.retriever import RetrievedChunk
from app.services.answer_service import AnswerService


EVAL_CASES = Path('eval/marketplace_answer_cases.jsonl')


def _load_cases() -> list[dict]:
    return [json.loads(line) for line in EVAL_CASES.read_text(encoding='utf-8').splitlines() if line.strip()]


def _ondo_chunk() -> RetrievedChunk:
    return RetrievedChunk(
        text=(
            'TECHNICAL SPECIFICATIONS\n'
            '- Номинальное давление: 1.6 МПа\n'
            '- Фитинги аксиальные совместимы с полимерными трубами: '
            'Наружный диаметр трубы 16 мм с толщиной стенки 2,2мм и 20 мм с толщиной стенки 2,8 мм\n'
            'MATERIALS\n'
            '- Корпус фитингов: горячештампованная латунь\n'
            'CONNECTIONS\n'
            '- Тип резьбы: трубная\n'
            'DESCRIPTION\n'
            '- Конструкция соединения не заужает внутренний диаметр трубопровода.\n'
            'FAQ\n'
            'Работы по монтажу аксиальных фитингов должны выполняться с помощью комплекта '
            'специального инструмента: ручного; электрического.'
        ),
        metadata={'manufacturer': 'Sabie S.r.l.', 'country': 'Italy', 'source_file': 'ondo_axial_fittings_rag_ready.txt'},
        score=0.6,
    )


def _deterministic_answer(query: str) -> str:
    chunks = [_ondo_chunk()]
    return (
        AnswerService._format_pipe_compatibility_answer(query, chunks)
        or AnswerService._format_known_or_missing_spec_answer(query, chunks)
    )


def test_marketplace_answer_cases_are_valid_jsonl():
    cases = _load_cases()
    assert cases
    assert all(case.get('id') and case.get('query') and case.get('expects') for case in cases)


def test_marketplace_answer_cases_pass_deterministic_answers():
    for case in _load_cases():
        answer = _deterministic_answer(case['query'])
        assert answer, case['id']
        assert check_answer(case, answer) == [], case['id']
