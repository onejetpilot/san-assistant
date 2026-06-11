from pathlib import Path

from app.rag.parser import parse_rag_file


def test_parse_metadata_and_articles(tmp_path: Path):
    p = tmp_path / 'x_rag_ready.txt'
    p.write_text(
        'DOCUMENT: x\nDOC_ID: x1\nPRODUCT: P\nCATEGORY: C\nBRAND: B\n\nARTICLES\n- ABC123\n\nVARIANTS (АРТИКУЛЫ)\n- ZZZ111 — desc\n',
        encoding='utf-8',
    )
    d = parse_rag_file(p)
    assert d.document == 'x'
    assert d.doc_id == 'x1'
    assert d.product == 'P'
    assert d.brand == 'B'
    assert any(a.original == 'ABC123' for a in d.articles)
    assert d.base_skus == ['ABC123']


def test_parse_collects_base_skus_from_k_suffix_articles(tmp_path: Path):
    p = tmp_path / 'kits_rag_ready.txt'
    p.write_text(
        'DOCUMENT: x\nDOC_ID: x1\nPRODUCT: P\nCATEGORY: C\nBRAND: B\n\nVARIANTS (АРТИКУЛЫ)\n- OXF02012K10 - desc\n',
        encoding='utf-8',
    )
    d = parse_rag_file(p)
    assert d.articles[0].normalized == 'OXF02012K10'
    assert d.articles[0].base_sku == 'OXF02012'
    assert d.base_skus == ['OXF02012']


def test_missing_sections_ok(tmp_path: Path):
    p = tmp_path / 'y_rag_ready.txt'
    p.write_text('DOCUMENT: y\nDOC_ID: y1\nPRODUCT: P\nCATEGORY: C\nBRAND: B\n', encoding='utf-8')
    d = parse_rag_file(p)
    assert d.sections == {}
