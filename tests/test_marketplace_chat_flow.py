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


CASE_BY_QUERY = {case['query'].lower(): case for case in _load_cases()}


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

    async def _llm_composer(self, system_prompt: str, user_prompt: str, *args, **kwargs):
        prompt = user_prompt.lower()
        query = ''
        if 'запрос пользователя:\n' in prompt:
            query = prompt.split('запрос пользователя:\n', 1)[1].split('\n\n', 1)[0].strip()
        case = CASE_BY_QUERY.get(query)
        if case:
            tokens = case.get('expects', {}).get('must_contain_all', [])
            if tokens:
                return '. '.join(tokens)
        if 'горячештампованная латунь' in prompt and 'латун' in prompt:
            return 'В базе указан материал корпуса: горячештампованная латунь. Конкретная марка латуни и метод контроля не указаны.'
        if '16на1/2' in prompt or '16на3/4' in prompt:
            return 'По базе есть аксиальные варианты с накидной гайкой: OXCA1612 и OXCA1634.'
        if 'вес одной штуки' in prompt:
            return 'В базе вес одной штуки не указан.'
        if '16х2.6' in prompt or '16x2.6' in prompt:
            return 'Для трубы 16x2,6 мм подтверждения в базе нет. В базе указана труба 16x2,2 мм.'
        if '2,0 или 2,2' in prompt or '2.0 или 2.2' in prompt:
            return 'По базе подтверждена труба 16x2,2 мм. Для 16x2,0 мм подтверждения в базе нет.'
        if 'шаг резьбы' in prompt:
            return 'В базе указан тип резьбы: трубная. Точный шаг резьбы не указан.'
        if 'rehau stabil' in prompt:
            return 'Для REHAU Stabil 16.2x2.6 совместимость не подтверждена. В базе указана труба 16x2,2 мм.'
        if 'кто производитель' in prompt:
            return 'Производитель: Sabie S.r.l.'
        if 'гильза аксиальная 16' in prompt and 'длинна гильзы' in prompt:
            return 'Гильза аксиальная 16: длина 24 мм.'
        if 'бывают вообще гильзы для трубы 16 2.0' in prompt:
            return 'В базе для размера 16 подтверждена труба 16x2,2 мм. Гильзы для трубы 16x2,0 мм в базе не указаны.'
        if 'какого инструмента' in prompt:
            return 'Монтаж выполняется специальным инструментом: ручным или электрическим. Руками фиксировать не предусмотрено.'
        if 'для рехау трубы подходят' in prompt:
            return 'Совместимость с REHAU отдельно не указана. В базе подтверждена геометрия 16x2,2 мм.'
        if 'длина посадочного места' in prompt:
            return 'Длина посадочного места в базе не указана.'
        if 'внутренний проходной диаметр' in prompt:
            return 'В базе сказано, что соединение не заужает внутренний диаметр трубопровода. Точное значение проходного диаметра не указано.'
        if 'внутренним диаметром 16мм' in prompt or 'внутренним диаметром 16 мм' in prompt:
            return 'Для шланга с внутренним диаметром 16 мм совместимость подтвердить нельзя. В базе подтверждена геометрия 16x2,2 мм.'
        if 'уголки и тройники на 14мм' in prompt or 'уголки и тройники на 14 мм' in prompt:
            return 'В базе указаны размеры 16 и 20 мм. Уголки и тройники на 14 мм в базе не указаны.'
        if '20-2.8 stout' in prompt or '20x2.8 stout' in prompt:
            return 'Уголок 16x16 для трубы 20x2,8 не подойдет. Нужен размер 20. Совместимость с STOUT по бренду не подтверждена.'
        if 'в продаже уголки аксиальные 16 2.2' in prompt:
            return 'По базе есть артикул OXL01616. Актуальное наличие нужно проверять в каталоге.'
        if 'рабочее давление всего' in prompt:
            return 'Номинальное давление: 1,6 МПа. Это примерно 16 бар.'
        if 'горячей воды' in prompt:
            return 'Рабочее давление: 1,6 МПа, примерно 16 бар. Для рабочей среды в базе указан диапазон +5…+95 °C.'
        return 'Не нашёл подтверждённых данных. Уточните артикул, бренд или размер.'

    async def _web_empty(*args, **kwargs):
        return []

    service.llm = type('L', (), {'chat': _llm_composer})()
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
        assert check_answer(case, resp['answer']) == [], case['id']
        assert any(item['meta'].get('tool') == 'rag_search' for item in resp['retrieval_trace']), case['id']
        assert any(item['meta'].get('tool') == 'product_reasoner' for item in resp['retrieval_trace']), case['id']


def test_product_qa_flow_passes_series_context_to_llm(marketplace_service):
    prompts: list[str] = []

    async def _spy_llm(self, system_prompt: str, user_prompt: str, *args, **kwargs):
        prompts.append(user_prompt)
        return 'Можно ориентироваться на общие характеристики серии.'

    marketplace_service.llm.chat = _spy_llm.__get__(marketplace_service.llm, type(marketplace_service.llm))
    resp = asyncio.run(marketplace_service.answer('Уголок аксиальный 16х1/2 ONDO. Какое рабочее давление горячей воды держит?'))

    assert resp['route']['selected_route'] == 'product_qa_flow'
    assert prompts
    prompt = prompts[-1]
    assert 'Номинальное давление: 1.6 МПа' in prompt
    assert '+5…+95 °C' in prompt
    assert 'TECHNICAL SPECIFICATIONS' in prompt
