import chromadb

from app.core.config import settings
from app.rag.parser import ParsedRagDocument


def build_product_cards(docs: list[ParsedRagDocument]) -> list[dict]:
    cards = []
    for d in docs:
        cards.append({
            'doc_id': d.doc_id,
            'product': d.product,
            'brand': d.brand,
            'category': d.category,
            'model': d.model,
            'aliases': d.aliases,
            'description': (d.sections.get('DESCRIPTION').content if d.sections.get('DESCRIPTION') else ''),
            'purpose': (d.sections.get('PURPOSE').content if d.sections.get('PURPOSE') else ''),
            'important': (d.sections.get('IMPORTANT').content if d.sections.get('IMPORTANT') else ''),
            'key_facts': (d.sections.get('KEY FACTS').content if d.sections.get('KEY FACTS') else ''),
            'article_count': len(d.articles),
        })
    return cards


def upsert_product_cards(cards: list[dict], recreate: bool = False) -> None:
    client = chromadb.PersistentClient(path=settings.CHROMA_PATH)
    if recreate:
        try:
            client.delete_collection(settings.CHROMA_COLLECTION_PRODUCT_CARDS)
        except Exception:
            pass
    collection = client.get_or_create_collection(settings.CHROMA_COLLECTION_PRODUCT_CARDS)
    normalized = []
    for c in cards:
        row = dict(c)
        if isinstance(row.get('aliases'), list):
            row['aliases'] = ', '.join(row['aliases'])
        normalized.append(row)
    ids = [c['doc_id'] for c in normalized]
    docs = [f"{c['product']} {c['brand']} {c['category']} {c['description']} {c['purpose']}" for c in normalized]
    metas = normalized
    if ids:
        collection.upsert(ids=ids, documents=docs, metadatas=metas)
