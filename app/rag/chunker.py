import re

from pydantic import BaseModel, Field

from app.rag.parser import ParsedRagDocument
from app.utils.article_normalizer import normalize_article


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
            'articles': ', '.join([a.original for a in doc.articles]),
            'source_file': doc.source_file,
        },
    )


def _mk_article_row(doc: ParsedRagDocument, section: str, line: str, idx: int) -> Chunk | None:
    row = line.strip().lstrip('-').strip()
    if not row:
        return None
    splitter = ' - ' if ' - ' in row else ' – ' if ' – ' in row else ''
    if splitter:
        article, description = row.split(splitter, 1)
    else:
        article, description = row, ''
    article = article.strip()
    if not re.match(r'^[A-Za-zА-Яа-я0-9._\-/]+$', article):
        return None
    if not article or not normalize_article(article):
        return None

    is_kit = 'шт' in description.lower()
    body = f"{section}\n{article}"
    if description:
        body += f" - {description.strip()}"
    chunk = _mk(doc, 'article_row', section, body, idx)
    chunk.id = f'{doc.doc_id}:article_row:{normalize_article(article)}:{idx}'
    chunk.metadata.update({
        'article': article,
        'article_normalized': normalize_article(article),
        'is_kit': is_kit,
    })
    return chunk


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

    variants = doc.sections.get('VARIANTS (АРТИКУЛЫ)')
    if variants and variants.content:
        for j, line in enumerate(variants.content.splitlines(), start=1):
            chunk = _mk_article_row(doc, 'VARIANTS (АРТИКУЛЫ)', line, j)
            if chunk:
                chunks.append(chunk)
    return chunks
