from app.rag.parser import ParsedRagDocument, RagSection
from app.rag.chunker import build_chunks


def test_chunker_sections_metadata():
    d = ParsedRagDocument(
        source_file='x.txt', document='x', doc_id='d1', product='P', category='C', brand='B',
        sections={
            'DESCRIPTION': RagSection(name='DESCRIPTION', content='desc'),
            'TECHNICAL SPECIFICATIONS': RagSection(name='TECHNICAL SPECIFICATIONS', content='spec'),
        },
    )
    chunks = build_chunks(d)
    assert chunks
    assert chunks[0].metadata['product'] == 'P'
    assert chunks[0].metadata['brand'] == 'B'
