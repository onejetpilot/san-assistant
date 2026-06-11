import asyncio

import pytest

from app.indexes.kit_index import KitIndex
from app.indexes.sku_index import SkuIndex, SkuRecord
from app.rag.retriever import RetrievedChunk
from app.services.answer_service import AnswerService
from app.utils.article_normalizer import normalize_article, normalize_sku


def _sku(article: str, short_description: str, article_type: str) -> SkuRecord:
    return SkuRecord(
        article=article,
        product='Фитинги аксиальные ONDO',
        brand='ONDO',
        category='Фитинги и соединения',
        model='Аксиальные',
        doc_id='ondo_axial',
        source_file='ondo_axial_fittings_rag_ready.txt',
        short_description=short_description,
        article_type=article_type,
    )


class BuyerQuestionLLM:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def chat(self, system_prompt: str, user_prompt: str, *args, **kwargs) -> str:
        self.prompts.append(user_prompt)
        prompt = user_prompt.lower()
        if 'oxl01616' in prompt and '20x2.8' in prompt:
            return 'Не подходит. OXL01616 это размер 16, а для трубы 20x2,8 нужен фитинг на 20 мм, например OXL02020.'
        if 'oxlw1612' in prompt and '16x2.0' in prompt:
            return 'Не подтверждено. В документации для размера 16 указана труба 16x2,2 мм, а для 16x2,0 подтверждения нет.'
        if 'oxf02012k10' in prompt and '1/2 это 15 или 20' in prompt:
            return '20 относится к трубе. 1/2 это размер трубной резьбы, а не 15 или 20 мм трубы.'
        if 'oxlf1612' in prompt and 'горячей воды' in prompt:
            return 'Можно ориентироваться на общие характеристики серии: рабочее давление 1,6 МПа, это примерно 16 бар, температура до +95 °C.'
        if 'oxt02020k10' in prompt and 'стяжк' in prompt:
            return 'Можно, если соблюдать правила серии. Скрытый монтаж и замоноличивание допустимы после гидравлических испытаний и с изоляцией от цементного раствора.'
        if 'oxf02012' in prompt and 'что за артикул' in prompt:
            return 'Артикул OXF02012: аксиальное соединение ONDO 20x1/2.'
        return 'Не подтверждено. В документации недостаточно данных для уверенного вывода.'


def _chunk() -> RetrievedChunk:
    return RetrievedChunk(
        text=(
            'PRODUCT: Фитинги аксиальные ONDO\n'
            'DESCRIPTION\n'
            '- Аксиальные фитинги для полимерных труб PEX.\n'
            'TECHNICAL SPECIFICATIONS\n'
            '- Номинальное давление: 1.6 МПа\n'
            '- Диапазон температуры рабочей среды: +5…+95 °C\n'
            '- Фитинги аксиальные совместимы с полимерными трубами: наружный диаметр трубы 16 мм с толщиной стенки 2,2 мм '
            'и 20 мм с толщиной стенки 2,8 мм\n'
            'VARIANTS (АРТИКУЛЫ)\n'
            'OXL01616 - диаметр(мм) 16х16\n'
            'OXL02020 - диаметр(мм) 20х20\n'
            'OXT02020 - диаметр(мм) 20x20x20\n'
            'OXF02012 - диаметр(мм х дюйм) 20х1/2\n'
            'OXLF1612 - диаметр(мм х дюйм) 16х1/2\n'
            'OXLW1612 - диаметр(мм х дюйм) 16х1/2\n'
            'CONNECTIONS\n'
            '- Тип резьбы: трубная\n'
            '- OXLF1612 - уголок с внутренней резьбой\n'
            '- OXF02012 - соединение с внутренней резьбой\n'
            'INSTALLATION\n'
            '- Допускается скрытый монтаж и замоноличивание соединений при условии гидравлических испытаний.\n'
            '- Соединение должно быть изолировано от цементного раствора.\n'
            'KEY FACTS\n'
            '- Размеры 16 и 20 относятся к трубе PEX, 1/2 и 3/4 относятся к трубной резьбе.'
        ),
        metadata={
            'doc_id': 'ondo_axial',
            'product': 'Фитинги аксиальные ONDO',
            'brand': 'ONDO',
            'category': 'Фитинги и соединения',
            'section_group': 'technical',
            'section': 'TECHNICAL SPECIFICATIONS',
            'source_file': 'ondo_axial_fittings_rag_ready.txt',
        },
        score=0.8,
    )


@pytest.fixture
def marketplace_service(monkeypatch):
    monkeypatch.setattr('app.services.answer_service.save_chat_request', lambda **k: None)
    monkeypatch.setattr('app.services.answer_service.save_knowledge_gap', lambda **k: None)
    monkeypatch.setattr('app.services.answer_service.get_current_index_versions', lambda: {})

    service = AnswerService.__new__(AnswerService)
    llm = BuyerQuestionLLM()
    sku_rows = [
        _sku('OXL01616', 'диаметр(мм) 16х16', 'уголки аксиальные'),
        _sku('OXL02020', 'диаметр(мм) 20х20', 'уголки аксиальные'),
        _sku('OXT02020', 'диаметр(мм) 20x20x20', 'тройники аксиальные'),
        _sku('OXF02012', 'диаметр(мм х дюйм) 20х1/2', 'соединения аксиальные с внутренней резьбой'),
        _sku('OXLF1612', 'диаметр(мм х дюйм) 16х1/2', 'уголки аксиальные с внутренней резьбой'),
        _sku('OXLW1612', 'диаметр(мм х дюйм) 16х1/2', 'уголки аксиальные с внутренней резьбой'),
    ]
    service.sku = SkuIndex({normalize_article(row.article): row.model_dump() for row in sku_rows})
    service.kits = KitIndex({
        'OXF02012K10': {
            'kit_article': 'OXF02012K10',
            'doc_id': 'kits',
            'source_file': 'kits.txt',
            'components': ['10 шт OXF02012'],
            'component_articles': ['OXF02012'],
        },
        'OXT02020K10': {
            'kit_article': 'OXT02020K10',
            'doc_id': 'kits',
            'source_file': 'kits.txt',
            'components': ['10 шт OXT02020'],
            'component_articles': ['OXT02020'],
        },
    })
    service.rag = type('R', (), {'available': True, 'search': lambda self, q: [_chunk()]})()
    service.docs = type('D', (), {'search': lambda self, *a, **k: []})()
    service.llm = llm
    service.memory = type('M', (), {
        'ensure_session': lambda self, sid: sid or 'test-session',
        'ensure_conversation': lambda self, sid, cid=None: cid or sid,
        'get_state': lambda self, *a, **k: {'current_article': 'OLD00001'},
        'get_recent_messages': lambda self, *a, **k: [{'role': 'user', 'content': 'старый артикул OLD00001'}],
        'append_message': lambda self, *a, **k: None,
        'update_state': lambda self, *a, **k: None,
    })()
    return service, llm


def test_normalize_sku_strips_kit_suffix():
    normalized = normalize_sku('OXF02012K10')
    assert normalized.normalized == 'OXF02012K10'
    assert normalized.base_article == 'OXF02012'
    assert normalized.had_kit_suffix


def test_compatibility_for_20x28_rejects_16mm_and_suggests_size_20(marketplace_service):
    service, _ = marketplace_service
    resp = asyncio.run(service.answer('Подойдет ли OXL01616 под трубу 20x2.8?'))
    text = resp['answer'].lower()
    assert 'не подходит' in text or 'не подойдет' in text
    assert '16' in text
    assert 'oxl02020' in text


def test_compatibility_for_16x20_is_not_confirmed_and_mentions_16x22(marketplace_service):
    service, _ = marketplace_service
    resp = asyncio.run(service.answer('Подойдет ли OXLW1612 для трубы 16x2.0?'))
    text = resp['answer'].lower()
    assert 'не подтвержден' in text
    assert '16x2,2' in text
    assert 'oxt02020' not in text


def test_thread_vs_pipe_dimension_is_explained_from_base_sku(marketplace_service):
    service, _ = marketplace_service
    resp = asyncio.run(service.answer('У OXF02012K10 1/2 это 15 или 20?'))
    text = resp['answer'].lower()
    assert '20' in text
    assert 'трубе' in text or 'труба' in text
    assert '1/2' in text
    assert 'резьб' in text


def test_hot_water_pressure_uses_series_limits(marketplace_service):
    service, _ = marketplace_service
    resp = asyncio.run(service.answer('Какое давление горячей воды держит OXLF1612?'))
    text = resp['answer'].lower()
    assert '1,6 мпа' in text or '1.6 мпа' in text
    assert '16 бар' in text
    assert '+95' in text


def test_screed_installation_uses_series_installation_rules(marketplace_service):
    service, _ = marketplace_service
    resp = asyncio.run(service.answer('Можно ли OXT02020K10 замоноличивать в стяжку?'))
    text = resp['answer'].lower()
    assert 'можно' in text
    assert 'гидравлическ' in text
    assert 'цемент' in text


def test_new_sku_does_not_reuse_previous_article_context(marketplace_service):
    service, llm = marketplace_service
    asyncio.run(service.answer('Что за артикул OXF02012?'))
    asyncio.run(service.answer('Подойдет ли OXL01616 под трубу 20x2.8?'))
    second_prompt = llm.prompts[-1].lower()
    assert 'old00001' not in second_prompt
    assert 'старый артикул' not in second_prompt
