from app.core import embedding_client
from app.core.config import settings
from app.rag import retriever as retriever_module
from app.rag.retriever import RagRetriever, RetrievedChunk
from app.rag.reranker import LexicalOverlapReranker


class _Collection:
    def query(self, query_embeddings, n_results, where=None):
        docs = [
            'TECHNICAL SPECIFICATIONS\nНоминальное давление: 1.6 МПа',
            'INSTALLATION\nДопускается скрытый монтаж',
            'CONNECTIONS\nТип резьбы: трубная',
            'faq другого товара',
        ]
        metas = [
            {'doc_id': 'ondo_axial', 'section': 'TECHNICAL SPECIFICATIONS', 'section_group': 'technical'},
            {'doc_id': 'ondo_axial', 'section': 'INSTALLATION', 'section_group': 'installation'},
            {'doc_id': 'ondo_axial', 'section': 'CONNECTIONS', 'section_group': 'connections'},
            {'doc_id': 'other_doc', 'section': 'FAQ', 'section_group': 'faq'},
        ]
        dists = [0.1, 0.12, 0.15, 0.4]
        if where and where.get('doc_id'):
            filtered = [(d, m, dist) for d, m, dist in zip(docs, metas, dists) if m.get('doc_id') == where['doc_id']]
        else:
            filtered = list(zip(docs, metas, dists))
        return {
            'documents': [[item[0] for item in filtered]],
            'metadatas': [[item[1] for item in filtered]],
            'distances': [[item[2] for item in filtered]],
        }

    def get(self, include=None, where=None):
        docs = [
            'VARIANTS (АРТИКУЛЫ)\nOXF02012 - 20x1/2',
            'CONNECTIONS\nТип резьбы: трубная',
            'TECHNICAL SPECIFICATIONS\nНоминальное давление: 1.6 МПа',
            'INSTALLATION\nДопускается скрытый монтаж',
            'LIMITATIONS\nНе подтверждать шланги',
            'KEY FACTS\n20 это труба, 1/2 это резьба',
            'FAQ\nМонтаж делать инструментом',
            'FAQ\nДругой товар',
        ]
        metas = [
            {'doc_id': 'ondo_axial', 'section': 'VARIANTS (АРТИКУЛЫ)', 'section_group': 'variants'},
            {'doc_id': 'ondo_axial', 'section': 'CONNECTIONS', 'section_group': 'connections'},
            {'doc_id': 'ondo_axial', 'section': 'TECHNICAL SPECIFICATIONS', 'section_group': 'technical'},
            {'doc_id': 'ondo_axial', 'section': 'INSTALLATION', 'section_group': 'installation'},
            {'doc_id': 'ondo_axial', 'section': 'LIMITATIONS', 'section_group': 'limitations'},
            {'doc_id': 'ondo_axial', 'section': 'KEY FACTS', 'section_group': 'key_facts'},
            {'doc_id': 'ondo_axial', 'section': 'FAQ', 'section_group': 'faq'},
            {'doc_id': 'other_doc', 'section': 'FAQ', 'section_group': 'faq'},
        ]
        if where and where.get('doc_id'):
            filtered = [(d, m) for d, m in zip(docs, metas) if m.get('doc_id') == where['doc_id']]
        else:
            filtered = list(zip(docs, metas))
        return {
            'documents': [item[0] for item in filtered],
            'metadatas': [item[1] for item in filtered],
        }


def test_rag_unavailable_without_embeddings(monkeypatch):
    monkeypatch.setattr(embedding_client.settings, 'EMBEDDING_API_KEY', '')
    monkeypatch.setattr(embedding_client.settings, 'EMBEDDING_BASE_URL', '')
    monkeypatch.setattr(retriever_module.EmbeddingClient, 'is_configured', staticmethod(lambda: False))

    rag = RagRetriever()

    assert not rag.available
    assert rag.search('аксиальные фитинги') == []


def test_rag_filters_low_score_chunks(monkeypatch):
    monkeypatch.setattr(retriever_module.EmbeddingClient, 'is_configured', staticmethod(lambda: True))
    monkeypatch.setattr(retriever_module.EmbeddingClient, 'embed_texts_sync', lambda self, texts: [[0.1, 0.2]])
    monkeypatch.setattr(retriever_module, 'get_chroma_client', lambda: type('Client', (), {'get_or_create_collection': lambda self, name, embedding_function=None: _Collection()})())
    monkeypatch.setattr(retriever_module.SkuIndex, 'load', classmethod(lambda cls, path: cls({})))
    monkeypatch.setattr(settings, 'RAG_MIN_SCORE', 0.35)

    rag = RagRetriever()
    results = rag.search('аксиальные фитинги')

    assert rag.available
    assert results
    assert results[0].metadata['doc_id'] == 'ondo_axial'


def test_document_aware_retrieval_adds_mandatory_sections_for_resolved_sku(monkeypatch):
    monkeypatch.setattr(retriever_module.EmbeddingClient, 'is_configured', staticmethod(lambda: True))
    monkeypatch.setattr(retriever_module.EmbeddingClient, 'embed_texts_sync', lambda self, texts: [[0.1, 0.2]])
    monkeypatch.setattr(retriever_module, 'get_chroma_client', lambda: type('Client', (), {'get_or_create_collection': lambda self, name, embedding_function=None: _Collection()})())
    monkeypatch.setattr(
        retriever_module.SkuIndex,
        'load',
        classmethod(lambda cls, path: cls({'OXF02012': {
            'article': 'OXF02012',
            'product': 'Фитинги аксиальные ONDO',
            'brand': 'ONDO',
            'category': 'Фитинги',
            'model': 'Аксиальные',
            'doc_id': 'ondo_axial',
            'source_file': 'ondo.txt',
            'short_description': '20x1/2',
            'base_sku': 'OXF02012',
        }})),
    )

    rag = RagRetriever()
    results = rag.search('Что означает 1/2 у OXF02012K10?')
    sections = {item.metadata.get('section') for item in results}

    assert 'CONNECTIONS' in sections
    assert 'VARIANTS (АРТИКУЛЫ)' in sections
    assert 'KEY FACTS' in sections
    assert all(item.metadata.get('doc_id') == 'ondo_axial' for item in results)


def test_document_aware_retrieval_anchors_to_confident_doc_without_sku(monkeypatch):
    monkeypatch.setattr(retriever_module.EmbeddingClient, 'is_configured', staticmethod(lambda: True))
    monkeypatch.setattr(retriever_module.EmbeddingClient, 'embed_texts_sync', lambda self, texts: [[0.1, 0.2]])
    monkeypatch.setattr(retriever_module, 'get_chroma_client', lambda: type('Client', (), {'get_or_create_collection': lambda self, name, embedding_function=None: _Collection()})())
    monkeypatch.setattr(retriever_module.SkuIndex, 'load', classmethod(lambda cls, path: cls({})))

    rag = RagRetriever()
    results = rag.search('Можно ли в стяжку и какое давление?')

    assert results
    assert all(item.metadata.get('doc_id') == 'ondo_axial' for item in results)
    sections = {item.metadata.get('section') for item in results}
    assert 'INSTALLATION' in sections
    assert 'TECHNICAL SPECIFICATIONS' in sections


def test_lexical_reranker_prefers_query_terms():
    chunks = [
        RetrievedChunk(text='общий текст про фитинги', metadata={'doc_id': 'generic'}, score=0.5),
        RetrievedChunk(text='паспорт насос ondo инструкция монтаж', metadata={'doc_id': 'specific'}, score=0.49),
    ]

    ranked = LexicalOverlapReranker().rerank('паспорт насос ondo', chunks)

    assert ranked[0].metadata['doc_id'] == 'specific'
