import asyncio
import json
from pathlib import Path

import pytest

from app.evaluation.run_answer_eval import check_answer
from app.indexes.kit_index import KitIndex
from app.indexes.sku_index import SkuIndex
from app.rag.retriever import RetrievedChunk
from app.services.answer_service import AnswerService


EVAL_CASES = Path('eval/marketplace_answer_cases.jsonl')


def _load_cases() -> list[dict]:
    return [json.loads(line) for line in EVAL_CASES.read_text(encoding='utf-8').splitlines() if line.strip()]


def _ondo_chunk() -> RetrievedChunk:
    return RetrievedChunk(
        text=(
            'PRODUCT: Фитинги аксиальные ONDO\n'
            'TECHNICAL SPECIFICATIONS\n'
            '- Номинальное давление: 1.6 МПа\n'
            '- Диапазон температуры рабочей среды: +5…+95 °C\n'
            '- Фитинги аксиальные совместимы с полимерными трубами: '
            'Наружный диаметр трубы 16 мм с толщиной стенки 2,2мм и 20 мм с толщиной стенки 2,8 мм\n'
            'VARIANTS (АРТИКУЛЫ)\n'
            'OXS00016 - внутренний диаметр(мм) 16, длина(мм) 24, наружный диаметр(мм) 21,5\n'
            'OXL01616 - диаметр(мм) 16х16\n'
            'OXL02020 - диаметр(мм) 20х20\n'
            'OXLF1612 - диаметр(мм х дюйм) 16х1/2\n'
            'OXLM1612 - диаметр(мм х дюйм) 16х1/2\n'
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
        metadata={
            'doc_id': 'ondo_axial',
            'product': 'Фитинги аксиальные ONDO',
            'brand': 'ONDO',
            'category': 'Фитинги и соединения',
            'manufacturer': 'Sabie S.r.l.',
            'country': 'Italy',
            'section_group': 'technical',
            'section': 'TECHNICAL SPECIFICATIONS',
            'source_file': 'ondo_axial_fittings_rag_ready.txt',
        },
        score=0.6,
    )


@pytest.fixture
def marketplace_service(monkeypatch):
    monkeypatch.setattr('app.services.answer_service.save_chat_request', lambda **k: None)
    monkeypatch.setattr('app.services.answer_service.save_knowledge_gap', lambda **k: None)
    monkeypatch.setattr('app.services.answer_service.get_current_index_versions', lambda: {})

    service = AnswerService.__new__(AnswerService)
    service.sku = SkuIndex({})
    service.kits = KitIndex({})
    service.rag = type('R', (), {'available': True, 'search': lambda self, q: [_ondo_chunk()]})()
    service.docs = type('D', (), {'search': lambda self, *a, **k: []})()

    async def _llm_forbidden(*args, **kwargs):
        raise AssertionError('marketplace deterministic answers should not call LLM')

    async def _web_empty(*args, **kwargs):
        return []

    service.llm = type('L', (), {'chat': _llm_forbidden})()
    service.web = type('W', (), {'search': _web_empty})()
    service.memory = type('M', (), {
        'ensure_session': lambda self, sid: sid or 'marketplace-session',
        'ensure_conversation': lambda self, sid, cid=None: cid or sid,
        'get_state': lambda self, *a, **k: {},
        'get_recent_messages': lambda self, *a, **k: [],
        'append_message': lambda self, *a, **k: None,
        'update_state': lambda self, *a, **k: None,
    })()
    service.expander = type('E', (), {'expand': lambda self, q: q})()
    return service


def test_marketplace_cases_pass_full_answer_service_flow(marketplace_service):
    for case in _load_cases():
        resp = asyncio.run(marketplace_service.answer(case['query']))
        assert 'llm' not in resp['tools_used'], case['id']
        assert check_answer(case, resp['answer']) == [], case['id']
        assert any(item['meta'].get('tool') == 'rag_search' for item in resp['retrieval_trace']), case['id']
