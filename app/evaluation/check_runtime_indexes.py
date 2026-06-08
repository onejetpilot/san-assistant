from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from app.core.chroma import get_chroma_client
from app.core.config import settings


COMPONENT_RE = re.compile(r'\d+\s*шт\.?\s*[A-Za-zА-Яа-я0-9._\-/]{4,}', flags=re.IGNORECASE)


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise RuntimeError(f'Index file is missing: {path}')
    return json.loads(path.read_text(encoding='utf-8'))


def _invalid_component_rows(data: dict, field: str) -> list[str]:
    invalid: list[str] = []
    for article, row in data.items():
        components = row.get(field) or []
        if components and not all(COMPONENT_RE.search(str(component)) for component in components):
            invalid.append(str(article))
    return invalid


def check_runtime_indexes(require_documents: bool = False) -> dict:
    client = get_chroma_client()
    product_chunks = client.get_or_create_collection(
        settings.CHROMA_COLLECTION_PRODUCT_CHUNKS,
        embedding_function=None,
    ).count()
    documents = client.get_or_create_collection(
        settings.CHROMA_COLLECTION_DOCUMENTS,
        embedding_function=None,
    ).count()
    product_cards = client.get_or_create_collection(
        settings.CHROMA_COLLECTION_PRODUCT_CARDS,
        embedding_function=None,
    ).count()

    indexes_path = Path(settings.INDEXES_PATH)
    sku = _load_json(indexes_path / 'sku_index.json')
    kits = _load_json(indexes_path / 'kit_index.json')

    errors: list[str] = []
    if product_chunks <= 0:
        errors.append('product_chunks collection is empty')
    if require_documents and documents <= 0:
        errors.append('documents collection is empty')
    if not sku:
        errors.append('sku_index is empty')
    if not kits:
        errors.append('kit_index is empty')

    dirty_sku = _invalid_component_rows(sku, 'kit_components')
    dirty_kits = _invalid_component_rows(kits, 'components')
    if dirty_sku:
        errors.append(f'sku_index has invalid kit_components, examples: {dirty_sku[:10]}')
    if dirty_kits:
        errors.append(f'kit_index has invalid components, examples: {dirty_kits[:10]}')

    result = {
        'product_chunks': product_chunks,
        'documents': documents,
        'product_cards': product_cards,
        'sku_count': len(sku),
        'kit_count': len(kits),
        'dirty_sku_count': len(dirty_sku),
        'dirty_kit_count': len(dirty_kits),
        'status': 'ok' if not errors else 'error',
        'errors': errors,
    }
    if errors:
        raise RuntimeError(json.dumps(result, ensure_ascii=False))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--require-documents', action='store_true')
    args = parser.parse_args()
    result = check_runtime_indexes(require_documents=args.require_documents)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
