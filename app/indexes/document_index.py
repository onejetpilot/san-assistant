from __future__ import annotations

import argparse
from datetime import datetime, timezone
from uuid import uuid4
from pathlib import Path
import yaml
import chromadb

from app.core.config import settings
from app.storage.db import SessionLocal
from app.storage.models import DocumentIndexRun
from app.documents.storage import get_storage_provider
from app.core.embedding_client import EmbeddingClient

ALLOWED_TYPES = {'passport', 'certificate', 'manual', 'installation_manual', 'warranty', 'datasheet', 'other'}


def load_documents_metadata(path: str) -> list[dict]:
    data = yaml.safe_load(Path(path).read_text(encoding='utf-8')) or {}
    docs = data.get('documents', [])
    return docs


def validate_documents_metadata(docs: list[dict], repo_root: str) -> None:
    for d in docs:
        for req in ['doc_id', 'title', 'product', 'brand', 'category', 'type', 'file_path', 'public_url']:
            if not d.get(req):
                raise ValueError(f'missing {req} in {d}')
        if d['type'] not in ALLOWED_TYPES:
            raise ValueError(f"invalid type {d['type']}")
        if not Path(repo_root, d['file_path']).exists():
            raise ValueError(f"file_path does not exist: {d['file_path']}")


def build_document_index(docs: list[dict], recreate: bool = False) -> None:
    client = chromadb.PersistentClient(path=settings.CHROMA_PATH)
    if recreate:
        try:
            client.delete_collection(settings.CHROMA_COLLECTION_DOCUMENTS)
        except Exception:
            pass
    col = client.get_or_create_collection(settings.CHROMA_COLLECTION_DOCUMENTS)
    provider = get_storage_provider()
    normalized = []
    for d in docs:
        d = dict(d)
        d['public_url'] = provider.resolve_public_url(d)
        if isinstance(d.get('articles'), list):
            d['articles'] = ', '.join(d['articles'])
        normalized.append(d)
    ids = [d['doc_id'] for d in normalized]
    bodies = [f"{d['title']} {d['product']} {d['brand']} {d['category']} {d['type']} {d.get('articles', '')}" for d in normalized]
    vectors = EmbeddingClient().embed_texts_sync(bodies)
    col.upsert(ids=ids, documents=bodies, embeddings=vectors, metadatas=normalized)


def run(recreate: bool = False) -> None:
    docs = load_documents_metadata(settings.DOCUMENTS_METADATA_PATH)
    validate_documents_metadata(docs, settings.DOCUMENTS_REPO_PATH)
    build_document_index(docs, recreate=recreate)

    session = SessionLocal()
    index_version = f"docs-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"
    type_counts: dict[str, int] = {}
    for d in docs:
        type_counts[d['type']] = type_counts.get(d['type'], 0) + 1
    session.add(DocumentIndexRun(
        status='ok',
        documents_count=len(docs),
        document_types_count_json=type_counts,
        index_version=index_version,
        indexed_at=datetime.now(timezone.utc),
    ))
    session.commit()
    session.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--recreate', action='store_true')
    args = parser.parse_args()
    run(recreate=args.recreate)
