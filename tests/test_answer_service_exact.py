import asyncio

from app.indexes.kit_index import KitIndex, KitRecord
from app.indexes.sku_index import SkuIndex, SkuRecord
from app.rag.retriever import RetrievedChunk
from app.services.answer_service import AnswerService
from app.utils.article_normalizer import normalize_article


def _sku(article: str, short_description: str = '') -> SkuRecord:
    return SkuRecord(
        article=article,
        product='Фитинги аксиальные ONDO',
        brand='ONDO',
        category='Фитинги и соединения',
        model='Аксиальные',
        doc_id='ondo_axial',
        source_file='ondo_axial_fittings_rag_ready.txt',
        short_description=short_description,
        article_type='соединения аксиальные с внутренней резьбой',
    )


def test_format_exact_sku_answer():
    answer = AnswerService._format_sku_answer(
        _sku('OXF01612', 'диаметр(мм х дюйм) 16х1/2, длина(мм) 37,5')
    )

    assert 'Артикул OXF01612' in answer
    assert 'Фитинги аксиальные ONDO' in answer
    assert 'ONDO' in answer
    assert '16х1/2' in answer
    assert '37,5' in answer


def test_format_exact_kit_answer_with_component_descriptions():
    service = AnswerService.__new__(AnswerService)
    component = _sku('OXF01612', 'диаметр(мм х дюйм) 16х1/2, длина(мм) 37,5')
    sleeve = _sku('OXS00016', 'внутренний диаметр(мм) 16, длина(мм) 24')
    service.sku = SkuIndex(
        {
            normalize_article(component.article): component.model_dump(),
            normalize_article(sleeve.article): sleeve.model_dump(),
        }
    )
    kit = KitRecord(
        kit_article='OXF01612K10G',
        doc_id='kits',
        source_file='kits_rag_ready.txt',
        components=['10 шт OXF01612', '10 шт OXS00016'],
        component_articles=['OXF01612', 'OXS00016'],
    )

    answer = service._format_kit_answer(kit)

    assert 'Состав комплекта OXF01612K10G' in answer
    assert '10 шт OXF01612' in answer
    assert '10 шт OXS00016' in answer
    assert 'OXF01612 — диаметр(мм х дюйм) 16х1/2' in answer
    assert 'OXS00016 — внутренний диаметр(мм) 16' in answer


def test_collect_relevant_context_keeps_single_document():
    service = AnswerService.__new__(AnswerService)
    service.rag = type('R', (), {
        'search': lambda self, q: [
            RetrievedChunk(
                text='TECHNICAL SPECIFICATIONS\nНоминальное давление: 1.6 МПа',
                metadata={'doc_id': 'ondo_axial', 'section': 'TECHNICAL SPECIFICATIONS', 'section_group': 'technical'},
                score=0.8,
            ),
            RetrievedChunk(
                text='FAQ\nДругой товар',
                metadata={'doc_id': 'other_doc', 'section': 'FAQ', 'section_group': 'faq'},
                score=0.7,
            ),
        ]
    })()

    chunks = service._collect_relevant_context(
        query='Какое давление у OXF01612?',
        requested_article='OXF01612',
        matched_sku=_sku('OXF01612', 'диаметр(мм х дюйм) 16х1/2'),
    )

    assert len(chunks) == 1
    assert chunks[0].metadata['doc_id'] == 'ondo_axial'


def test_answer_returns_no_data_without_internet(monkeypatch):
    monkeypatch.setattr('app.services.answer_service.save_chat_request', lambda **k: None)
    monkeypatch.setattr('app.services.answer_service.save_knowledge_gap', lambda **k: None)
    monkeypatch.setattr('app.services.answer_service.get_current_index_versions', lambda: {})

    service = AnswerService.__new__(AnswerService)
    service.sku = SkuIndex({})
    service.kits = KitIndex({})
    service.rag = type('R', (), {'available': True, 'search': lambda self, q: []})()
    service.docs = type('D', (), {'search': lambda self, *a, **k: []})()
    service.llm = type('L', (), {'chat': lambda self, *a, **k: 'unused'})()
    service.memory = type('M', (), {
        'ensure_session': lambda self, sid: sid or 's1',
        'ensure_conversation': lambda self, sid, cid=None: cid or sid,
        'get_state': lambda self, *a, **k: {},
        'append_message': lambda self, *a, **k: None,
        'update_state': lambda self, *a, **k: None,
    })()

    resp = asyncio.run(service.answer('Что известно про неизвестный товар?'))

    assert resp['used_web_search'] is False
    assert resp['web_results'] == []
    assert 'нет данных' in resp['answer'].lower()
