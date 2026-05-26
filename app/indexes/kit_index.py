from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import BaseModel, Field

from app.rag.parser import ParsedRagDocument
from app.utils.article_normalizer import normalize_article


class KitRecord(BaseModel):
    kit_article: str
    doc_id: str
    source_file: str
    components: list[str] = Field(default_factory=list)
    component_articles: list[str] = Field(default_factory=list)


class KitIndex:
    def __init__(self, data: dict[str, dict] | None = None) -> None:
        self.data = data or {}

    def lookup(self, article: str) -> KitRecord | None:
        row = self.data.get(normalize_article(article))
        return KitRecord(**row) if row else None

    def save(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding='utf-8')

    @classmethod
    def load(cls, path: str) -> 'KitIndex':
        p = Path(path)
        if not p.exists():
            return cls({})
        return cls(json.loads(p.read_text(encoding='utf-8')))


def build_kit_index(docs: list[ParsedRagDocument]) -> KitIndex:
    out: dict[str, dict] = {}
    for doc in docs:
        variants = doc.sections.get('VARIANTS (АРТИКУЛЫ)')
        if not variants or not variants.content:
            continue
        for raw in variants.content.splitlines():
            line = raw.strip().lstrip('-').strip()
            if not line:
                continue
            m = re.match(r'^([A-Za-zА-Яа-я0-9._\-/]+)\s*[-—:]\s*(.+)$', line)
            if not m:
                continue
            kit_article = m.group(1).strip()
            rhs = m.group(2).strip()
            components = _extract_components(rhs)
            if not components:
                continue
            component_articles = [_extract_article_from_component(c) for c in components]
            component_articles = [x for x in component_articles if x]
            norm = normalize_article(kit_article)
            out[norm] = KitRecord(
                kit_article=kit_article,
                doc_id=doc.doc_id,
                source_file=doc.source_file,
                components=components,
                component_articles=component_articles,
            ).model_dump()
    return KitIndex(out)


def _extract_components(rhs: str) -> list[str]:
    parts: list[str] = []
    for chunk in rhs.split('+'):
        token = re.sub(r'\s+', ' ', chunk.strip())
        if not token:
            continue
        m = re.search(r'(\d+\s*шт\.?\s*[A-Za-zА-Яа-я0-9._\-/]+)', token, flags=re.IGNORECASE)
        if m:
            parts.append(re.sub(r'\s+', ' ', m.group(1)).strip())
        else:
            a = re.search(r'([A-Za-zА-Яа-я0-9._\-/]{4,})', token)
            if a:
                parts.append(a.group(1))
    return parts


def _extract_article_from_component(text: str) -> str:
    m = re.search(r'([A-Za-zА-Яа-я0-9._\-/]{4,})$', text.strip())
    return m.group(1) if m else ''
