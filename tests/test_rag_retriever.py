from app.core import embedding_client
from app.core.config import settings
from app.rag import retriever as retriever_module
from app.rag.retriever import RagRetriever


class _Collection:
    def query(self, query_embeddings, n_results):
        return {
            'documents': [['strong chunk', 'weak chunk']],
            'metadatas': [[{'doc_id': 'strong'}, {'doc_id': 'weak'}]],
            'distances': [[0.2, 0.9]],
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
    monkeypatch.setattr(settings, 'RAG_MIN_SCORE', 0.35)

    rag = RagRetriever()
    results = rag.search('аксиальные фитинги')

    assert rag.available
    assert [item.metadata['doc_id'] for item in results] == ['strong']
