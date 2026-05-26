from app.documents.document_search import DocumentSearch


def test_document_search_no_hallucination(monkeypatch):
    s = DocumentSearch()
    monkeypatch.setattr(s.collection, 'get', lambda include: {'metadatas': []})
    monkeypatch.setattr(s.collection, 'query', lambda query_texts, n_results: {'metadatas': [[]], 'distances': [[]]})
    assert s.search('nothing') == []
