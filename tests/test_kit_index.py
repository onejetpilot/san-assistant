from app.indexes.kit_index import build_kit_index
from app.rag.parser import ParsedRagDocument, RagSection


def test_build_global_kit_index():
    d = ParsedRagDocument(
        source_file='kb/a.txt',
        doc_id='d1',
        product='P',
        category='C',
        brand='B',
        sections={
            'VARIANTS (АРТИКУЛЫ)': RagSection(
                name='VARIANTS (АРТИКУЛЫ)',
                content='- OXF02012K01G - 1 шт OXF02012 + 1 шт OXS00020',
            ),
        },
    )
    idx = build_kit_index([d])
    row = idx.lookup('oxf02012k01g')
    assert row is not None
    assert row.components == ['1 шт OXF02012', '1 шт OXS00020']
    assert row.component_articles == ['OXF02012', 'OXS00020']


def test_build_global_kit_index_single_component():
    d = ParsedRagDocument(
        source_file='kb/a.txt',
        doc_id='d1',
        product='P',
        category='C',
        brand='B',
        sections={
            'VARIANTS (АРТИКУЛЫ)': RagSection(
                name='VARIANTS (АРТИКУЛЫ)',
                content='- OXS00016K10 - 10 шт OXS00016',
            ),
        },
    )
    idx = build_kit_index([d])
    row = idx.lookup('OXS00016K10')
    assert row is not None
    assert row.components == ['10 шт OXS00016']
    assert row.component_articles == ['OXS00016']


def test_does_not_treat_regular_variant_as_kit():
    d = ParsedRagDocument(
        source_file='kb/a.txt',
        doc_id='d1',
        product='P',
        category='C',
        brand='B',
        sections={
            'VARIANTS (АРТИКУЛЫ)': RagSection(
                name='VARIANTS (АРТИКУЛЫ)',
                content='OXF01612 - диаметр(мм х дюйм) 16х1/2, длина(мм) 37,5',
            ),
        },
    )
    idx = build_kit_index([d])
    assert idx.lookup('OXF01612') is None
