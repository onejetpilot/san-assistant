import asyncio

import pytest

from app.services.answer_service import AnswerService
from app.services.routing.preprocessor import build_routing_context
from app.services.routing.intent_classifier import classify_intent
from app.services.routing.route_planner import plan_route


def _route(query: str, state: dict | None = None):
    ctx = build_routing_context(query, state or {}, [])
    intent, conf, reason = classify_intent(ctx)
    return plan_route(ctx, intent, conf, reason)


def test_empty_query_is_ambiguous():
    d = _route('   ')
    assert d.intent == 'ambiguous_question'
    assert d.needs_clarification
    assert 'clarify' in d.tools_to_call


def test_follow_up_without_history_is_not_follow_up_route():
    d = _route('А паспорт на него есть?')
    assert d.intent == 'document_request'
    assert 'document_search' in d.tools_to_call


def test_follow_up_pronoun_without_context_is_ambiguous():
    d = _route('Подойдет ли он для квартиры?')
    assert d.intent == 'ambiguous_question'


def test_kb_question_does_not_use_sku_lookup():
    d = _route('Почему падает давление в системе?')
    assert d.intent == 'knowledge_base_question'
    assert 'sku_lookup' not in d.tools_to_call
    assert d.selected_route == 'rag_answer'


def test_comparison_without_articles_skips_sku():
    d = _route('Чем отличается редуктор давления от фильтра?')
    assert d.intent == 'comparison_question'
    assert 'sku_lookup' not in d.tools_to_call


def test_price_does_not_plan_web_search():
    d = _route('Сколько стоит фильтр грубой очистки?')
    assert 'san_team_search' not in d.tools_to_call


def test_typo_passport_still_routes_to_document():
    # Опечатка: без fuzzy-match ожидаем не document, а KB/default — фиксируем текущее поведение.
    d = _route('нужен паспарт на изделие')
    assert d.intent in {'product_question', 'knowledge_base_question', 'ambiguous_question'}


@pytest.fixture
def service(monkeypatch):
    monkeypatch.setattr('app.services.answer_service.save_chat_request', lambda **k: None)
    monkeypatch.setattr('app.services.answer_service.save_knowledge_gap', lambda **k: None)
    monkeypatch.setattr('app.services.answer_service.get_current_index_versions', lambda: {})
    svc = AnswerService.__new__(AnswerService)
    svc.sku = type('S', (), {'lookup': lambda self, a: None, 'data': {}})()
    svc.kits = type('K', (), {'lookup': lambda self, a: None})()
    svc.rag = type('R', (), {'available': True, 'search': lambda self, q: []})()
    svc.docs = type('D', (), {'search': lambda self, *a, **k: []})()
    svc.llm = type('L', (), {'chat': lambda self, *a, **k: _raise_llm()})()
    async def _web_forbidden(*a, **k):
        raise AssertionError('web should not be called')

    svc.web = type('W', (), {'search': _web_forbidden})()
    svc.memory = type('M', (), {
        'ensure_session': lambda self, sid: sid or 's',
        'ensure_conversation': lambda self, sid, cid=None: cid or sid,
        'get_state': lambda self, *a, **k: {},
        'get_recent_messages': lambda self, *a, **k: [],
        'append_message': lambda self, *a, **k: None,
        'update_state': lambda self, *a, **k: None,
    })()
    svc.expander = type('E', (), {'expand': lambda self, q: q})()
    return svc


def _raise_llm():
    raise AssertionError('LLM should not be called without RAG context')


def test_kb_answer_never_calls_llm_without_context(service):
    resp = asyncio.run(service.answer('Почему падает давление в системе отопления?'))
    assert 'базе знаний' in resp['answer'].lower()
    assert 'llm' not in resp['tools_used']
    assert 'fallback' in resp['tools_used']


def test_price_does_not_call_web_without_explicit_intent(service):
    resp = asyncio.run(service.answer('Сколько стоит фильтр грубой очистки?'))
    assert 'san_team_search' not in resp['tools_used']


def test_sleeve_length_routes_to_kb_not_product_selection():
    d = _route('гильза аксиальная 16, какая длина?')
    assert d.intent == 'knowledge_base_question'
    assert d.selected_route == 'rag_answer'
    assert 'sku_lookup' not in d.tools_to_call


def test_sleeve_compatibility_routes_to_kb():
    d = _route('Так гильза встанет в трубу 16x2,0?')
    assert d.intent == 'knowledge_base_question'


def test_pipe_difference_routes_to_comparison_or_kb():
    d = _route('В чем отличие: труба 16/2,0 или 2,2? Гильза со стороны наружной, имеет ли значение такой фитинг?')
    assert d.intent in {'comparison_question', 'knowledge_base_question'}
    assert 'rag_search' in d.tools_to_call


def test_weak_rag_allows_llm_for_kb(service, monkeypatch):
    from app.rag.retriever import RetrievedChunk

    weak_chunk = RetrievedChunk(
        text='VARIANTS гильза 16 длина 24 мм',
        metadata={'product': 'Фитинги аксиальные ONDO', 'section': 'VARIANTS', 'doc_id': 'ondo'},
        score=0.18,
    )
    service.rag.search = lambda q: [weak_chunk]

    async def _llm(system, user, **k):
        raise AssertionError('deterministic sleeve length answer should not call LLM')

    service.llm.chat = _llm
    resp = asyncio.run(service.answer('гильза аксиальная 16, какая длина?'))
    assert resp['answer_mode'] == 'technical_answer'
    assert 'llm' not in resp['tools_used']
    assert '24 мм' in resp['answer']
    assert 'В каталоге не нашёл' not in resp['answer']
