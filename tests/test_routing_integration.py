from __future__ import annotations

import asyncio

import pytest

from app.indexes.kit_index import KitIndex
from app.indexes.sku_index import SkuIndex, SkuRecord
from app.rag.retriever import RetrievedChunk
from app.services.answer_service import AnswerService
from app.services.routing.rag_quality import build_no_context_fallback, has_strong_rag_context
from app.utils.article_normalizer import normalize_article


def _sku(article: str) -> SkuRecord:
    return SkuRecord(
        article=article,
        product='Фитинги аксиальные ONDO',
        brand='ONDO',
        category='Фитинги',
        model='Аксиальные',
        doc_id='ondo',
        source_file='ondo.txt',
        short_description='диаметр 16',
    )


@pytest.fixture
def service(monkeypatch):
    monkeypatch.setattr('app.services.answer_service.save_chat_request', lambda **k: None)
    monkeypatch.setattr('app.services.answer_service.save_knowledge_gap', lambda **k: None)
    monkeypatch.setattr('app.services.answer_service.get_current_index_versions', lambda: {})
    svc = AnswerService.__new__(AnswerService)
    sku = _sku('OXF01612')
    svc.sku = SkuIndex({normalize_article(sku.article): sku.model_dump()})
    svc.kits = KitIndex({})
    svc.rag = type('R', (), {'available': True, 'search': lambda self, q: []})()
    svc.docs = type('D', (), {'search': lambda self, *a, **k: []})()
    svc.llm = type('L', (), {'chat': lambda self, *a, **k: 'LLM_SHOULD_NOT_BE_CALLED'})()
    svc.web = type('W', (), {'search': lambda self, q: []})()
    svc.memory = type('M', (), {
        'ensure_session': lambda self, sid: sid or 'test-session',
        'ensure_conversation': lambda self, sid, cid=None: cid or sid,
        'get_state': lambda self, *a, **k: {},
        'get_recent_messages': lambda self, *a, **k: [],
        'append_message': lambda self, *a, **k: None,
        'update_state': lambda self, *a, **k: None,
    })()
    svc.expander = type('E', (), {'expand': lambda self, q: q})()
    return svc


def test_out_of_scope_refuses(service):
    resp = asyncio.run(service.answer('Напиши мне стих'))
    assert 'сантехническ' in resp['answer'].lower()
    assert 'refuse' in resp['tools_used']


def test_smalltalk_returns_greeting(service):
    resp = asyncio.run(service.answer('Привет'))
    assert 'помогу' in resp['answer'].lower() or 'здравствуйте' in resp['answer'].lower()
    assert resp['tools_used'] == ['smalltalk']


def test_ambiguous_asks_clarification(service):
    resp = asyncio.run(service.answer('Что лучше?'))
    assert resp['answer_mode'] == 'clarify'
    assert 'clarify' in resp['tools_used']


def test_article_lookup_uses_sku_not_llm(service):
    resp = asyncio.run(service.answer('Что за OXF01612?', answer_style='short'))
    assert 'OXF01612' in resp['answer']
    assert 'sku_lookup' in resp['tools_used']
    assert resp['retrieval_trace'][0]['meta']['tool'] == 'sku_lookup'
    assert resp['retrieval_trace'][0]['status'] == 'ok'
    assert 'LLM_SHOULD_NOT_BE_CALLED' not in resp['answer']


def test_no_rag_context_fallback(service):
    async def _no_llm(*a, **k):
        raise AssertionError('LLM must not be called without RAG context')

    service.llm.chat = _no_llm
    resp = asyncio.run(service.answer('Почему падает давление в системе отопления?'))
    assert 'базе знаний' in resp['answer'].lower()
    assert 'fallback' in resp['tools_used']
    assert 'llm' not in resp['tools_used']


def test_rag_strong_context_threshold():
    weak = [RetrievedChunk(text='x', metadata={}, score=0.2)]
    strong = [RetrievedChunk(text='x', metadata={}, score=0.5)]
    assert not has_strong_rag_context(weak)
    assert has_strong_rag_context(strong)


def test_no_context_fallback_messages():
    assert 'документ' in build_no_context_fallback('document_request').lower()
    assert 'каталог' in build_no_context_fallback('product_question').lower()
    assert 'базе знаний' in build_no_context_fallback('knowledge_base_question').lower()
