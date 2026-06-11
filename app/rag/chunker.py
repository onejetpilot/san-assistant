import re

from pydantic import BaseModel, Field

from app.rag.parser import ParsedRagDocument
from app.utils.article_normalizer import normalize_article, normalize_sku


class Chunk(BaseModel):
    id: str
    text: str
    metadata: dict = Field(default_factory=dict)


def _mk(doc: ParsedRagDocument, section_group: str, section: str, body: str, idx: int) -> Chunk:
    header = (
        f"PRODUCT: {doc.product}\n"
        f"BRAND: {doc.brand}\n"
        f"CATEGORY: {doc.category}\n"
        f"MODEL: {doc.model}\n"
        f"SECTION: {section}\n\n"
    )
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
            'base_skus': ', '.join(doc.base_skus),
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
    normalized = normalize_article(article)
    base_sku = normalize_sku(article).base_article or normalized
    chunk.metadata.update({
        'article': article,
        'article_normalized': normalized,
        'base_sku': base_sku,
        'is_kit': is_kit,
    })
    return chunk


def build_chunks(doc: ParsedRagDocument) -> list[Chunk]:
    section_groups = {
        'DESCRIPTION': 'description',
        'PURPOSE': 'purpose',
        'IMPORTANT': 'important',
        'VARIANTS (МОДЕЛИ)': 'variants',
        'VARIANTS (АРТИКУЛЫ)': 'variants',
        'FAQ': 'faq',
        'TECHNICAL SPECIFICATIONS': 'technical',
        'PERFORMANCE': 'technical',
        'MATERIALS': 'materials',
        'COMPONENTS': 'components',
        'CONNECTIONS': 'connections',
        'WORKING FLUID': 'technical',
        'INSTALLATION': 'installation',
        'STARTUP': 'installation',
        'OPERATION': 'operation',
        'ADJUSTMENT': 'operation',
        'LIMITATIONS': 'limitations',
        'MAINTENANCE': 'maintenance',
        'TROUBLESHOOTING': 'maintenance',
        'STORAGE AND TRANSPORT': 'storage',
        'WARRANTY': 'warranty',
        'ARTICLES': 'articles',
        'KEY FACTS': 'key_facts',
    }
    chunks: list[Chunk] = []
    i = 0
    for section_name, section_group in section_groups.items():
        section = doc.sections.get(section_name)
        if not section or not section.content:
            continue
        i += 1
        chunks.append(_mk(doc, section_group, section_name, f'{section_name}\n{section.content}', i))

    variants = doc.sections.get('VARIANTS (АРТИКУЛЫ)')
    if variants and variants.content:
        for j, line in enumerate(variants.content.splitlines(), start=1):
            chunk = _mk_article_row(doc, 'VARIANTS (АРТИКУЛЫ)', line, j)
            if chunk:
                chunks.append(chunk)
    return chunks
