from app.rag.parser import ParsedRagDocument, RagSection
from app.rag.chunker import build_chunks


def test_chunker_sections_metadata():
    d = ParsedRagDocument(
        source_file='x.txt', document='x', doc_id='d1', product='P', category='C', brand='B',
        base_skus=['OXF01612'],
        sections={
            'DESCRIPTION': RagSection(name='DESCRIPTION', content='desc'),
            'TECHNICAL SPECIFICATIONS': RagSection(name='TECHNICAL SPECIFICATIONS', content='spec'),
        },
    )
    chunks = build_chunks(d)
    assert chunks
    assert chunks[0].metadata['product'] == 'P'
    assert chunks[0].metadata['brand'] == 'B'
    assert chunks[0].metadata['base_skus'] == 'OXF01612'
    assert {chunk.metadata['section'] for chunk in chunks} == {'DESCRIPTION', 'TECHNICAL SPECIFICATIONS'}


def test_chunker_builds_article_row_chunks_for_variants():
    d = ParsedRagDocument(
        source_file='x.txt', document='x', doc_id='d1', product='P', category='C', brand='B',
        base_skus=['OXF01612'],
        sections={
            'VARIANTS (АРТИКУЛЫ)': RagSection(
                name='VARIANTS (АРТИКУЛЫ)',
                content='- OXF01612K01G - 2 шт OXF01612 + 1 шт OXS00016\n[НЕТ ДАННЫХ В ИСХОДНОМ ДОКУМЕНТЕ]',
            ),
        },
    )

    chunks = build_chunks(d)
    row_chunks = [c for c in chunks if c.metadata['section_group'] == 'article_row']

    assert len(row_chunks) == 1
    assert row_chunks[0].metadata['article'] == 'OXF01612K01G'
    assert row_chunks[0].metadata['article_normalized'] == 'OXF01612K01G'
    assert row_chunks[0].metadata['base_sku'] == 'OXF01612G'
    assert row_chunks[0].metadata['is_kit'] is True
    assert '2 шт OXF01612' in row_chunks[0].text
