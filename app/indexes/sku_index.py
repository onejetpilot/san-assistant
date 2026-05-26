from __future__ import annotations

import json
import re
from pathlib import Path
from pydantic import BaseModel

from app.rag.parser import ParsedRagDocument
from app.utils.article_normalizer import normalize_article


class SkuRecord(BaseModel):
    article: str
    product: str
    brand: str
    category: str
    model: str
    doc_id: str
    source_file: str
    short_description: str = ''
    article_type: str = ''
    related_articles: list[str] = []
    kit_components: list[str] = []
    matched_from: str = 'ARTICLES'


class SkuIndex:
    def __init__(self, data: dict[str, dict] | None = None) -> None:
        self.data = data or {}

    def lookup(self, article: str) -> SkuRecord | None:
        row = self.data.get(normalize_article(article))
        return SkuRecord(**row) if row else None

    def save(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding='utf-8')

    @classmethod
    def load(cls, path: str) -> 'SkuIndex':
        p = Path(path)
        if not p.exists():
            return cls({})
        return cls(json.loads(p.read_text(encoding='utf-8')))


def build_sku_index(docs: list[ParsedRagDocument]) -> SkuIndex:
    data: dict[str, dict] = {}
    for doc in docs:
        desc = (doc.sections.get('DESCRIPTION').content if doc.sections.get('DESCRIPTION') else '')[:240]
        related = [a.original for a in doc.articles]
        variants_text = doc.sections.get('VARIANTS (АРТИКУЛЫ)').content if doc.sections.get('VARIANTS (АРТИКУЛЫ)') else ''
        variants_map = _extract_variant_lines(variants_text)
        connections_text = doc.sections.get('CONNECTIONS').content if doc.sections.get('CONNECTIONS') else ''
        type_map = _extract_article_types(connections_text)
        for a in doc.articles:
            norm = normalize_article(a.original)
            variant_desc = variants_map.get(norm, '')
            kit_components = _extract_kit_components(variant_desc)
            short = variant_desc or desc
            data[norm] = SkuRecord(
                article=a.original,
                product=doc.product,
                brand=doc.brand,
                category=doc.category,
                model=doc.model,
                doc_id=doc.doc_id,
                source_file=doc.source_file,
                short_description=short[:240],
                article_type=type_map.get(norm, ''),
                related_articles=[x for x in related if normalize_article(x) != norm][:10],
                kit_components=kit_components,
                matched_from='ARTICLES',
            ).model_dump()
    return SkuIndex(data)


def _extract_variant_lines(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        line = line.lstrip('-').strip()
        m = re.match(r'^([A-Za-zА-Яа-я0-9._\-/]+)\s*[-—:]\s*(.+)$', line)
        if not m:
            continue
        article, desc = m.group(1).strip(), m.group(2).strip()
        out[normalize_article(article)] = desc
    return out


def _extract_kit_components(variant_desc: str) -> list[str]:
    if not variant_desc:
        return []
    parts: list[str] = []
    for chunk in variant_desc.split('+'):
        token = chunk.strip()
        if not token:
            continue
        # Keep readable kit part strings like: "1 шт OXF02012"
        m = re.search(r'(\d+\s*шт\.?\s*[A-Za-zА-Яа-я0-9._\-/]+)', token, flags=re.IGNORECASE)
        if m:
            parts.append(re.sub(r'\s+', ' ', m.group(1)).strip())
            continue
        art = re.search(r'([A-Za-zА-Яа-я0-9._\-/]{4,})', token)
        if art:
            parts.append(art.group(1))
    return parts


def _extract_article_types(connections_text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in connections_text.splitlines():
        line = raw.strip().lstrip('-').strip()
        if not line:
            continue
        if ' - ' in line:
            left, right = line.split(' - ', 1)
        elif ' – ' in line:
            left, right = line.split(' – ', 1)
        else:
            continue
        article_type = right.split('.')[0].strip().lower()
        articles = [x.strip() for x in left.split(',') if x.strip()]
        for a in articles:
            out[normalize_article(a)] = article_type
    return out
