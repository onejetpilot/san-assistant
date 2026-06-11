from app.rag.parser import ParsedRagDocument, ArticleItem, RagSection
from app.indexes.sku_index import build_sku_index


def test_case_insensitive_lookup():
    d = ParsedRagDocument(source_file='x', doc_id='d1', product='P', category='C', brand='B', articles=[ArticleItem(original='AbC123', normalized='abc123', base_sku='abc123')], base_skus=['abc123'])
    idx = build_sku_index([d])
    assert idx.lookup('ABC123') is not None


def test_lookup_from_articles():
    d = ParsedRagDocument(source_file='x', doc_id='d1', product='P', category='C', brand='B', articles=[ArticleItem(original='X1', normalized='x1', base_sku='x1')], base_skus=['x1'])
    idx = build_sku_index([d])
    assert idx.lookup('x1') is not None


def test_extract_kit_components_from_variants():
    d = ParsedRagDocument(
        source_file='x',
        doc_id='d1',
        product='P',
        category='C',
        brand='B',
        articles=[ArticleItem(original='OXF02012K01G', normalized='OXF02012K01G', base_sku='OXF02012G')],
        base_skus=['OXF02012G'],
        sections={
            'VARIANTS (АРТИКУЛЫ)': RagSection(
                name='VARIANTS (АРТИКУЛЫ)',
                content='- OXF02012K01G - 1 шт OXF02012 + 1 шт OXS00020',
            ),
        },
    )
    idx = build_sku_index([d])
    row = idx.lookup('OXF02012K01G')
    assert row is not None
    assert row.kit_components == ['1 шт OXF02012', '1 шт OXS00020']


def test_extract_single_component_kit():
    d = ParsedRagDocument(
        source_file='x',
        doc_id='d1',
        product='P',
        category='C',
        brand='B',
        articles=[ArticleItem(original='OXS00016K10', normalized='OXS00016K10', base_sku='OXS00016')],
        base_skus=['OXS00016'],
        sections={
            'VARIANTS (АРТИКУЛЫ)': RagSection(
                name='VARIANTS (АРТИКУЛЫ)',
                content='- OXS00016K10 - 10 шт OXS00016',
            ),
        },
    )
    idx = build_sku_index([d])
    row = idx.lookup('OXS00016K10')
    assert row is not None
    assert row.kit_components == ['10 шт OXS00016']
    assert row.base_sku == 'OXS00016'


def test_regular_variant_description_is_not_kit_components():
    d = ParsedRagDocument(
        source_file='x',
        doc_id='d1',
        product='P',
        category='C',
        brand='B',
        articles=[ArticleItem(original='OXF01612', normalized='OXF01612', base_sku='OXF01612')],
        base_skus=['OXF01612'],
        sections={
            'VARIANTS (АРТИКУЛЫ)': RagSection(
                name='VARIANTS (АРТИКУЛЫ)',
                content='OXF01612 - диаметр(мм х дюйм) 16х1/2, длина(мм) 37,5',
            ),
        },
    )
    idx = build_sku_index([d])
    row = idx.lookup('OXF01612')
    assert row is not None
    assert row.kit_components == []
