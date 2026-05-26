from pathlib import Path

from app.rag.validate_knowledge_base import validate_document


def test_fails_without_product(tmp_path: Path):
    p = tmp_path / 'a_rag_ready.txt'
    p.write_text('DOCUMENT: a\nDOC_ID: d\nCATEGORY: C\nBRAND: B\n', encoding='utf-8')
    e, _ = validate_document(p, {})
    assert any('PRODUCT' in x for x in e)


def test_fails_dn20_article(tmp_path: Path):
    p = tmp_path / 'b_rag_ready.txt'
    p.write_text('DOCUMENT: a\nDOC_ID: d\nPRODUCT: P\nCATEGORY: C\nBRAND: B\n\nARTICLES\n- DN20\n', encoding='utf-8')
    e, _ = validate_document(p, {})
    assert any('forbidden' in x for x in e)


def test_fails_article_description(tmp_path: Path):
    p = tmp_path / 'c_rag_ready.txt'
    p.write_text('DOCUMENT: a\nDOC_ID: d\nPRODUCT: P\nCATEGORY: C\nBRAND: B\n\nARTICLES\n- ABC123 — text\n', encoding='utf-8')
    e, _ = validate_document(p, {})
    assert e


def test_valid_document(tmp_path: Path):
    p = tmp_path / 'd_rag_ready.txt'
    p.write_text('DOCUMENT: a\nDOC_ID: d\nPRODUCT: P\nCATEGORY: C\nBRAND: B\n\nARTICLES\n- ABC123\n', encoding='utf-8')
    e, _ = validate_document(p, {})
    assert not e
