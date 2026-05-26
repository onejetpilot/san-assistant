from __future__ import annotations

import json
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
    related_articles: list[str] = []
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
        for a in doc.articles:
            norm = normalize_article(a.original)
            data[norm] = SkuRecord(
                article=a.original,
                product=doc.product,
                brand=doc.brand,
                category=doc.category,
                model=doc.model,
                doc_id=doc.doc_id,
                source_file=doc.source_file,
                short_description=desc,
                related_articles=[x for x in related if normalize_article(x) != norm][:10],
                matched_from='ARTICLES',
            ).model_dump()
    return SkuIndex(data)
