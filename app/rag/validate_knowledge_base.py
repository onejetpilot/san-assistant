from __future__ import annotations

import argparse
import re
from pathlib import Path

from app.core.config import settings
from app.rag.parser import parse_rag_file

FORBIDDEN_ARTICLE_TOKENS = {'DN20', 'PN25', 'G1/2', 'M30X1.5', 'IPX4', 'ГОСТ', 'СП', 'ФЗ', 'CW617N', 'CW614N', 'AISI304'}


class ValidationError(Exception):
    pass


def validate_document(path: str | Path, seen_articles: dict[str, str]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    p = Path(path)
    raw = p.read_text(encoding='utf-8-sig')
    if not raw.strip():
        errors.append(f'{p}: empty file')
        return errors, warnings

    doc = parse_rag_file(p)
    for req in ['document', 'doc_id', 'product', 'category', 'brand']:
        if not getattr(doc, req):
            errors.append(f'{p}: missing {req.upper()}')

    if 'TURN47FILE0' in raw:
        errors.append(f'{p}: contains OCR garbage token')

    for line in raw.splitlines():
        if len(line) > 2000:
            errors.append(f'{p}: line too long')
            break

    for a in doc.articles:
        upper = a.normalized.upper()
        if upper in FORBIDDEN_ARTICLE_TOKENS:
            errors.append(f'{p}: forbidden article token {a.original}')
        if re.search(r'\s|—|:', a.original):
            errors.append(f'{p}: article contains description {a.original}')

    variants = doc.sections.get('VARIANTS (АРТИКУЛЫ)')
    if variants and variants.content.strip():
        for line in variants.content.splitlines():
            l = line.strip().lstrip('-').strip()
            if not l:
                continue
            if not re.match(r'^[A-Za-z0-9._\-/]+\s*[—-]', l) and not re.match(r'^[A-Za-z0-9._\-/]+$', l):
                errors.append(f'{p}: VARIANTS (АРТИКУЛЫ) line must start from article: {l}')
                break

    local_seen: set[str] = set()
    for a in doc.articles:
        if a.normalized in local_seen:
            errors.append(f'{p}: duplicate article {a.original}')
        local_seen.add(a.normalized)

        previous = seen_articles.get(a.normalized)
        if previous and previous != doc.doc_id:
            errors.append(f'{p}: article conflict {a.original} between {previous} and {doc.doc_id}')
        else:
            seen_articles[a.normalized] = doc.doc_id

    return errors, warnings


def validate_knowledge_base(kb_path: str) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    seen_articles: dict[str, str] = {}
    files = sorted(Path(kb_path).glob('*_rag_ready.txt'))
    for path in files:
        e, w = validate_document(path, seen_articles)
        errors.extend(e)
        warnings.extend(w)
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--path', default=None)
    args = parser.parse_args()
    kb_path = args.path or settings.KNOWLEDGE_BASE_PATH
    errors, warnings = validate_knowledge_base(kb_path)
    for w in warnings:
        print(f'WARNING: {w}')
    if errors:
        for e in errors:
            print(f'ERROR: {e}')
        return 1
    print(f'Validation OK. warnings={len(warnings)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
