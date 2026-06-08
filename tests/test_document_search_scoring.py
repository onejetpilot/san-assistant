from app.documents.document_search import DocumentSearch


class _Collection:
    def get(self, include=None):
        return {
            'metadatas': [
                {'title': 'Паспорт OXF', 'type': 'passport', 'articles': 'OXF01612', 'public_url': 'u1', 'product': 'A', 'brand': 'ONDO'},
                {'title': 'Сертификат OXF', 'type': 'certificate', 'articles': 'OXF01612', 'public_url': 'u2', 'product': 'A', 'brand': 'ONDO'},
            ]
        }

    def query(self, query_embeddings, n_results):
        return {
            'metadatas': [[
                {'title': 'Сертификат OXF', 'type': 'certificate', 'articles': 'OXF01612', 'public_url': 'u2', 'product': 'A', 'brand': 'ONDO'},
                {'title': 'Паспорт OXF', 'type': 'passport', 'articles': 'OXF01612', 'public_url': 'u1', 'product': 'A', 'brand': 'ONDO'},
            ]],
            'distances': [[0.05, 0.4]],
        }


def test_document_search_prefers_requested_doc_type(monkeypatch):
    monkeypatch.setattr('app.documents.document_search.get_chroma_client', lambda: type('C', (), {'get_or_create_collection': lambda self, name, embedding_function=None: _Collection()})())
    monkeypatch.setattr('app.documents.document_search.EmbeddingClient.embed_texts_sync', lambda self, texts: [[0.1, 0.2]])

    search = DocumentSearch()
    results = search.search('нужен паспорт на OXF01612', article='OXF01612', doc_type='passport', top_k=2)

    assert results
    assert results[0]['type'] == 'passport'
    assert results[0]['public_url'] == 'u1'
