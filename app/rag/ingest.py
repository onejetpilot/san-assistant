from __future__ import annotations

import argparse
from pathlib import Path
from datetime import datetime
from uuid import uuid4

import chromadb

from app.core.config import settings
from app.rag.validate_knowledge_base import validate_knowledge_base
from app.rag.parser import parse_rag_file
from app.rag.chunker import build_chunks
from app.indexes.sku_index import build_sku_index
from app.indexes.product_card_index import build_product_cards, upsert_product_cards
from app.storage.db import SessionLocal
from app.storage.models import IngestionRun


def run(recreate: bool = False) -> None:
    errors, warnings = validate_knowledge_base(settings.KNOWLEDGE_BASE_PATH)
    if errors:
        index_version = f"rag-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"
        session = SessionLocal()
        session.add(IngestionRun(
            run_type='knowledge', status='failed', documents_count=0, chunks_count=0, sku_count=0,
            errors_json=errors, warnings_json=warnings, index_version=index_version,
        ))
        session.commit()
        session.close()
        raise RuntimeError('\n'.join(errors))

    files = sorted(Path(settings.KNOWLEDGE_BASE_PATH).glob('*_rag_ready.txt'))
    docs = [parse_rag_file(f) for f in files]

    all_chunks = []
    for doc in docs:
        all_chunks.extend(build_chunks(doc))

    cards = build_product_cards(docs)
    sku = build_sku_index(docs)

    client = chromadb.PersistentClient(path=settings.CHROMA_PATH)
    if recreate:
        try:
            client.delete_collection(settings.CHROMA_COLLECTION_PRODUCT_CHUNKS)
        except Exception:
            pass
    col = client.get_or_create_collection(settings.CHROMA_COLLECTION_PRODUCT_CHUNKS)
    if all_chunks:
        col.upsert(
            ids=[c.id for c in all_chunks],
            documents=[c.text for c in all_chunks],
            metadatas=[c.metadata for c in all_chunks],
        )

    upsert_product_cards(cards, recreate=recreate)
    sku.save('/data/indexes/sku_index.json')

    index_version = f"rag-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"
    session = SessionLocal()
    session.add(IngestionRun(
        run_type='knowledge', status='ok', documents_count=len(docs), chunks_count=len(all_chunks), sku_count=len(sku.data),
        errors_json=[], warnings_json=warnings, index_version=index_version,
    ))
    session.commit()
    session.close()
    print(f'Indexed at {datetime.utcnow().isoformat()} docs={len(docs)} chunks={len(all_chunks)} sku={len(sku.data)}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--recreate', action='store_true')
    args = parser.parse_args()
    run(recreate=args.recreate)
