from pydantic import BaseModel, Field

from app.rag.parser import ParsedRagDocument


class Chunk(BaseModel):
    id: str
    text: str
    metadata: dict = Field(default_factory=dict)


def _mk(doc: ParsedRagDocument, section_group: str, section: str, body: str, idx: int) -> Chunk:
    header = f"Product: {doc.product}\nBrand: {doc.brand}\nCategory: {doc.category}\nSection: {section}\n\n"
    return Chunk(
        id=f'{doc.doc_id}:{section_group}:{idx}',
        text=header + body.strip(),
        metadata={
            'doc_id': doc.doc_id,
            'document': doc.document,
            'product': doc.product,
            'category': doc.category,
            'brand': doc.brand,
            'model': doc.model,
            'manufacturer': doc.manufacturer,
            'country': doc.country,
            'aliases': ', '.join(doc.aliases),
            'section': section,
            'section_group': section_group,
            'articles': [a.original for a in doc.articles],
            'source_file': doc.source_file,
        },
    )


def build_chunks(doc: ParsedRagDocument) -> list[Chunk]:
    groups = {
        'overview': ['DESCRIPTION', 'PURPOSE', 'IMPORTANT', 'KEY FACTS'],
        'technical': ['TECHNICAL SPECIFICATIONS', 'PERFORMANCE', 'MATERIALS', 'WORKING FLUID'],
        'installation': ['INSTALLATION', 'STARTUP', 'OPERATION', 'ADJUSTMENT', 'LIMITATIONS', 'MAINTENANCE', 'TROUBLESHOOTING'],
        'articles': ['VARIANTS (АРТИКУЛЫ)', 'ARTICLES', 'CONNECTIONS', 'COMPONENTS'],
        'warranty_storage': ['WARRANTY', 'STORAGE AND TRANSPORT'],
    }
    chunks: list[Chunk] = []
    i = 0
    for gname, names in groups.items():
        parts = []
        for name in names:
            section = doc.sections.get(name)
            if section and section.content:
                parts.append(f'{name}\n{section.content}')
        if parts:
            i += 1
            chunks.append(_mk(doc, gname, ', '.join(names), '\n\n'.join(parts), i))

    faq = doc.sections.get('FAQ')
    if faq and faq.content:
        qa_raw = [x.strip() for x in faq.content.split('\nQ:') if x.strip()]
        for j, qa in enumerate(qa_raw, start=1):
            qtext = qa if qa.startswith('Q:') else f'Q:{qa}'
            chunks.append(_mk(doc, 'faq', 'FAQ', qtext, j))
    return chunks
