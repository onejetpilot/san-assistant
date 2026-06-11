import asyncio

import pytest

from app.indexes.kit_index import KitIndex
from app.indexes.sku_index import SkuIndex, SkuRecord
from app.rag.retriever import RetrievedChunk
from app.services.answer_service import AnswerService
from app.utils.article_normalizer import normalize_article


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


class SpyLLM:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def chat(self, system_prompt: str, user_prompt: str, *args, **kwargs) -> str:
        self.prompts.append(user_prompt)
        prompt = user_prompt.lower()
        if 'точное совпадение sku' in prompt and 'артикул: oxl01616' in prompt and 'intent: article_lookup' in prompt:
            return 'Артикул OXL01616 — уголок аксиальный ONDO 16x16.'
        if 'документы:' in prompt and 'паспорт ondo' in prompt:
            return 'Нашёл паспорт на товар: Паспорт ONDO — https://example.test/passport.pdf'
        if 'decision: not_compatible' in prompt:
            return 'Нет, не подойдет. Нужен размер 20, например OXL02020.'
        if 'decision: assortment_missing' in prompt:
            return 'В базе 14 мм не представлены. Для аксиальных уголков и тройников указаны размеры 16 и 20 мм.'
        if 'recommended_articles: oxs00016' in prompt:
            return 'Нужна гильза 16 мм, подходящий артикул OXS00016.'
        if 'decision: related_product_found' in prompt and '20' in prompt:
            return 'Нужна гильза 20 мм, подходящий артикул OXS00020.'
        if 'installation_not_confirmed' in prompt:
            return 'В базе нет подтверждения, что эти фитинги можно замоноличивать в стяжку.'
        if 'spec_missing' in prompt and 'вес' in prompt:
            return 'Вес одной штуки в базе не указан.'
        if 'not_confirmed' in prompt and 'внутреннему диаметру' in prompt:
            return 'Совместимость по внутреннему диаметру не подтверждена: аксиальные фитинги подбираются по наружному диаметру и толщине стенки.'
        return 'Нужны дополнительные данные для точного ответа.'


def _ondo_chunk() -> RetrievedChunk:
    return RetrievedChunk(
        text=(
            'PRODUCT: Фитинги аксиальные ONDO\n'
            'TECHNICAL SPECIFICATIONS\n'
            '- Фитинги аксиальные совместимы с полимерными трубами: '
            'Наружный диаметр трубы 16 мм с толщиной стенки 2,2мм и 20 мм с толщиной стенки 2,8 мм\n'
            'VARIANTS (АРТИКУЛЫ)\n'
            'OXS00016 - внутренний диаметр(мм) 16, длина(мм) 24\n'
            'OXS00020 - внутренний диаметр(мм) 20, длина(мм) 27\n'
            'OXL01616 - диаметр(мм) 16х16\n'
            'OXL02020 - диаметр(мм) 20х20\n'
            'OXT02020 - диаметр(мм) 20x20x20\n'
            'FAQ\n'
            'Монтаж аксиальных фитингов выполняется специальным инструментом.'
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
        score=0.7,
    )


@pytest.fixture
def marketplace_service(monkeypatch):
    monkeypatch.setattr('app.services.answer_service.save_chat_request', lambda **k: None)
    monkeypatch.setattr('app.services.answer_service.save_knowledge_gap', lambda **k: None)
    monkeypatch.setattr('app.services.answer_service.get_current_index_versions', lambda: {})

    service = AnswerService.__new__(AnswerService)
    llm = SpyLLM()
    sku_rows = [
        _sku('OXL01616', 'диаметр(мм) 16х16', 'уголки аксиальные'),
        _sku('OXL02020', 'диаметр(мм) 20х20', 'уголки аксиальные'),
        _sku('OXT02020', 'диаметр(мм) 20x20x20', 'тройники аксиальные'),
        _sku('OXS00016', 'внутренний диаметр(мм) 16, длина(мм) 24', 'гильзы аксиальные'),
        _sku('OXS00020', 'внутренний диаметр(мм) 20, длина(мм) 27', 'гильзы аксиальные'),
        _sku('OXF01612K10G', 'комплект 10 шт OXF01612 + 10 шт OXS00016', 'комплекты'),
    ]
    service.sku = SkuIndex({normalize_article(row.article): row.model_dump() for row in sku_rows})
    service.kits = KitIndex({})
    service.rag = type('R', (), {'available': True, 'search': lambda self, q: [_ondo_chunk()]})()
    service.docs = type('D', (), {'search': lambda self, *a, **k: []})()
    service.llm = llm
    service.web = type('W', (), {'search': lambda self, q: []})()
    service.memory = type('M', (), {
        'ensure_session': lambda self, sid: sid or 'test-session',
        'ensure_conversation': lambda self, sid, cid=None: cid or sid,
        'get_state': lambda self, *a, **k: {},
        'get_recent_messages': lambda self, *a, **k: [],
        'append_message': lambda self, *a, **k: None,
        'update_state': lambda self, *a, **k: None,
    })()
    service.expander = type('E', (), {'expand': lambda self, q: q})()
    service.reasoner = None
    return service, llm


def test_compatibility_question_uses_evidence_and_not_article_list(marketplace_service):
    service, llm = marketplace_service
    resp = asyncio.run(service.answer('Подойдет ли уголок OXL01616 под трубу 20х2.8?'))

    assert 'не подойдет' in resp['answer'].lower()
    assert 'OXL02020' in resp['answer'] or 'размер 20' in resp['answer']
    assert 'Артикулы' not in resp['answer']
    assert 'llm' in resp['tools_used']
    assert any('PRODUCT_EVIDENCE' in prompt and 'decision: not_compatible' in prompt for prompt in llm.prompts)


def test_assortment_question_reports_missing_14mm_without_generic_fallback(marketplace_service):
    service, _ = marketplace_service
    resp = asyncio.run(service.answer('Есть ли уголки и тройники на 14 мм?'))

    text = resp['answer'].lower()
    assert '14 мм' in text
    assert '16' in text and '20' in text
    assert 'не нашёл точной информации' not in text


def test_related_product_question_recommends_sleeve_for_20mm(marketplace_service):
    service, _ = marketplace_service
    resp = asyncio.run(service.answer('Какая гильза нужна к тройнику OXT02020?'))

    assert 'OXS00020' in resp['answer'] or 'гильза 20 мм' in resp['answer']
    assert 'описание' not in resp['answer'].lower()


def test_related_product_question_recommends_sleeve_for_16mm(marketplace_service):
    service, _ = marketplace_service
    resp = asyncio.run(service.answer('Какая гильза нужна для уголка 16 мм?'))

    assert 'OXS00016' in resp['answer'] or 'гильза 16 мм' in resp['answer']


def test_installation_question_is_not_reduced_to_article_list(marketplace_service):
    service, _ = marketplace_service
    resp = asyncio.run(service.answer('Можно ли прятать эти фитинги в стяжке?'))

    assert resp['route']['intent'] == 'installation_or_usage_question'
    assert 'артикул' not in resp['answer'].lower()
    assert 'стяжк' in resp['answer'].lower() or 'подтвержден' in resp['answer'].lower()


def test_weight_question_for_kit_reports_missing_piece_weight(marketplace_service):
    service, _ = marketplace_service
    resp = asyncio.run(service.answer('Какой вес одной штуки OXF01612K10G?'))

    assert 'вес одной штуки' in resp['answer'].lower()
    assert 'состав комплекта' not in resp['answer'].lower()
    reasoner_trace = next(item for item in resp['retrieval_trace'] if item['meta'].get('tool') == 'product_reasoner')
    assert reasoner_trace['results'][0]['decision'] == 'spec_missing'


def test_kit_lookup_does_not_become_final_answer_for_non_composition_question(marketplace_service):
    service, _ = marketplace_service
    resp = asyncio.run(service.answer('Подойдет ли OXF01612K10G для трубы 20х2.8?'))

    assert 'состав комплекта' not in resp['answer'].lower()
    assert any(item['meta'].get('tool') == 'product_reasoner' for item in resp['retrieval_trace'])


def test_inner_diameter_question_explains_selection_basis(marketplace_service):
    service, _ = marketplace_service
    resp = asyncio.run(service.answer('Подойдет ли тройник по внутреннему диаметру шланга 16 мм?'))

    text = resp['answer'].lower()
    assert 'внутреннему диаметру' in text
    assert 'наружному диаметру' in text
    assert 'толщине стенки' in text


def test_exact_article_lookup_still_returns_product_card(marketplace_service):
    service, llm = marketplace_service
    resp = asyncio.run(service.answer('Что за артикул OXL01616?'))

    assert 'OXL01616' in resp['answer']
    assert 'llm' in resp['tools_used']
    assert llm.prompts


def test_document_request_uses_llm_when_available(marketplace_service):
    service, llm = marketplace_service
    service.docs = type('D', (), {'search': lambda self, *a, **k: [{
        'title': 'Паспорт ONDO',
        'type': 'passport',
        'product': 'Фитинги аксиальные ONDO',
        'brand': 'ONDO',
        'public_url': 'https://example.test/passport.pdf',
    }]})()
    resp = asyncio.run(service.answer('Дай паспорт на OXL01616'))

    assert 'llm' in resp['tools_used']
    assert llm.prompts
    assert any('Документы:' in prompt or 'Паспорт ONDO' in prompt for prompt in llm.prompts)
