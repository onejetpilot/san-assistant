from app.rag.parser import ParsedRagDocument, ArticleItem
from app.indexes.sku_index import build_sku_index


def test_case_insensitive_lookup():
    d = ParsedRagDocument(source_file='x', doc_id='d1', product='P', category='C', brand='B', articles=[ArticleItem(original='AbC123', normalized='abc123')])
    idx = build_sku_index([d])
    assert idx.lookup('ABC123') is not None


def test_lookup_from_articles():
    d = ParsedRagDocument(source_file='x', doc_id='d1', product='P', category='C', brand='B', articles=[ArticleItem(original='X1', normalized='x1')])
    idx = build_sku_index([d])
    assert idx.lookup('x1') is not None
