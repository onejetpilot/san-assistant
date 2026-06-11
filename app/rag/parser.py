from __future__ import annotations

import re
from pathlib import Path
from pydantic import BaseModel, Field
from app.utils.article_normalizer import normalize_article, normalize_sku

META_FIELDS = ['DOCUMENT', 'DOC_ID', 'PRODUCT', 'CATEGORY', 'BRAND', 'MODEL', 'MANUFACTURER', 'COUNTRY', 'ALIASES']
SECTIONS = [
    'DESCRIPTION', 'PURPOSE', 'IMPORTANT', 'VARIANTS (МОДЕЛИ)', 'VARIANTS (АРТИКУЛЫ)', 'FAQ',
    'TECHNICAL SPECIFICATIONS', 'PERFORMANCE', 'MATERIALS', 'COMPONENTS', 'CONNECTIONS', 'WORKING FLUID',
    'INSTALLATION', 'STARTUP', 'OPERATION', 'ADJUSTMENT', 'LIMITATIONS', 'MAINTENANCE', 'TROUBLESHOOTING',
    'STORAGE AND TRANSPORT', 'WARRANTY', 'ARTICLES', 'KEY FACTS'
]


class ArticleItem(BaseModel):
    original: str
    normalized: str
    base_sku: str


class RagSection(BaseModel):
    name: str
    content: str = ''


class ParsedRagDocument(BaseModel):
    source_file: str
    document: str = ''
    doc_id: str = ''
    product: str = ''
    category: str = ''
    brand: str = ''
    model: str = ''
    manufacturer: str = ''
    country: str = ''
    aliases: list[str] = Field(default_factory=list)
    sections: dict[str, RagSection] = Field(default_factory=dict)
    articles: list[ArticleItem] = Field(default_factory=list)
    base_skus: list[str] = Field(default_factory=list)


def _extract_articles(text: str) -> list[str]:
    out: list[str] = []
    for line in text.splitlines():
        token = line.strip().lstrip('-').strip()
        if not token:
            continue
        match = re.match(r'^([A-Za-zА-Яа-я0-9._\-/]+)\s*(?:[-—:]\s*.+)?$', token)
        if match:
            token = match.group(1).strip()
        if re.match(r'^[A-Za-z0-9._\-/]+$', token):
            out.append(token)
    return out


def parse_rag_file(path: str | Path) -> ParsedRagDocument:
    raw = Path(path).read_text(encoding='utf-8-sig')
    lines = raw.splitlines()
    meta: dict[str, str] = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            # Allow visual separators inside metadata header block.
            i += 1
            continue
        matched = False
        for field in META_FIELDS:
            if line.startswith(f'{field}:'):
                meta[field] = line.split(':', 1)[1].strip()
                matched = True
                break
        if matched:
            i += 1
            continue
        break

    sections: dict[str, RagSection] = {}
    current = None
    buff: list[str] = []
    section_set = set(SECTIONS)
    for line in lines[i:]:
        s = line.strip()
        if s in section_set:
            if current is not None:
                sections[current] = RagSection(name=current, content='\n'.join(buff).strip())
            current = s
            buff = []
        else:
            buff.append(line)
    if current is not None:
        sections[current] = RagSection(name=current, content='\n'.join(buff).strip())

    articles = _extract_articles(sections.get('ARTICLES', RagSection(name='ARTICLES')).content)
    if not articles:
        articles = _extract_articles(sections.get('VARIANTS (АРТИКУЛЫ)', RagSection(name='VARIANTS (АРТИКУЛЫ)')).content)

    article_items = []
    for article in dict.fromkeys(articles):
        normalized = normalize_article(article)
        base_sku = normalize_sku(article).base_article or normalized
        article_items.append(ArticleItem(original=article, normalized=normalized, base_sku=base_sku))
    base_skus = list(dict.fromkeys([item.base_sku for item in article_items if item.base_sku]))

    aliases = [x.strip() for x in meta.get('ALIASES', '').split(',') if x.strip()]
    return ParsedRagDocument(
        source_file=str(path),
        document=meta.get('DOCUMENT', ''),
        doc_id=meta.get('DOC_ID', ''),
        product=meta.get('PRODUCT', ''),
        category=meta.get('CATEGORY', ''),
        brand=meta.get('BRAND', ''),
        model=meta.get('MODEL', ''),
        manufacturer=meta.get('MANUFACTURER', ''),
        country=meta.get('COUNTRY', ''),
        aliases=aliases,
        sections=sections,
        articles=article_items,
        base_skus=base_skus,
    )
