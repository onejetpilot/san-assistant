import yaml
from pathlib import Path

from app.core.config import settings
from app.core.chroma import get_chroma_client
from app.core.embedding_client import EmbeddingClient
from app.utils.article_normalizer import normalize_article


class DocumentSearch:
    def __init__(self) -> None:
        self.available = True
        self.collection = None
        self.fallback_docs = []
        meta_path = Path(settings.DOCUMENTS_METADATA_PATH)
        if meta_path.exists():
            data = yaml.safe_load(meta_path.read_text(encoding='utf-8')) or {}
            self.fallback_docs = data.get('documents', [])
        try:
            self.client = get_chroma_client()
            self.collection = self.client.get_or_create_collection(settings.CHROMA_COLLECTION_DOCUMENTS, embedding_function=None)
        except Exception:
            self.available = False

    def search(self, query: str, article: str | None = None, doc_type: str | None = None, top_k: int = 5) -> list[dict]:
        if not self.collection:
            return self._fallback_search(query, article, doc_type, top_k)
        all_rows = self.collection.get(include=['metadatas'])
        metas = all_rows.get('metadatas', [])
        out: list[dict] = []
        if article:
            norm = normalize_article(article)
            matched = [m for m in metas if norm in [normalize_article(x) for x in self._articles_as_list(m.get('articles'))]]
            if matched:
                out.extend([self._as_result(m, 0.99) for m in matched])
        try:
            qv = EmbeddingClient().embed_texts_sync([query])[0]
            res = self.collection.query(query_embeddings=[qv], n_results=top_k)
        except Exception:
            return self._fallback_search(query, article, doc_type, top_k)

        for m, dist in zip(res.get('metadatas', [[]])[0], res.get('distances', [[]])[0]):
            score = 1.0 - float(dist or 1.0)
            if doc_type and m.get('type') == doc_type:
                score += 0.12
            if article:
                norm = normalize_article(article)
                if norm in [normalize_article(x) for x in self._articles_as_list(m.get('articles'))]:
                    score += 0.2
            out.append(self._as_result(m, min(score, 1.0)))

        if doc_type:
            out = [row for row in out if row.get('type') == doc_type or row.get('score', 0) >= settings.DOCUMENT_MIN_SCORE]
        out = self._dedupe_and_sort(out, preferred_type=doc_type)
        return out[:top_k]

    @staticmethod
    def _as_result(m: dict, score: float) -> dict:
        articles = m.get('articles', [])
        if isinstance(articles, str):
            articles = [x.strip() for x in articles.split(',') if x.strip()]
        return {
            'title': m.get('title', ''),
            'type': m.get('type', 'other'),
            'product': m.get('product', ''),
            'brand': m.get('brand', ''),
            'category': m.get('category', ''),
            'articles': articles,
            'public_url': m.get('public_url', ''),
            'file_path': m.get('file_path', ''),
            'score': score,
        }

    @staticmethod
    def _articles_as_list(value) -> list[str]:
        if isinstance(value, list):
            return [str(x) for x in value]
        if isinstance(value, str):
            return [x.strip() for x in value.split(',') if x.strip()]
        return []

    def _fallback_search(self, query: str, article: str | None, doc_type: str | None, top_k: int) -> list[dict]:
        rows = self.fallback_docs
        if article:
            norm = normalize_article(article)
            hit = [r for r in rows if norm in [normalize_article(x) for x in self._articles_as_list(r.get('articles'))]]
            if hit:
                typed = [r for r in hit if not doc_type or r.get('type') == doc_type]
                source = typed or hit
                return [self._as_result(r, 0.95) for r in source[:top_k]]
        if doc_type:
            hit = [r for r in rows if r.get('type') == doc_type]
            if hit:
                return [self._as_result(r, 0.85) for r in hit[:top_k]]
        q = query.lower()
        hit = [r for r in rows if q in f"{r.get('title','')} {r.get('product','')} {r.get('brand','')} {r.get('category','')}".lower()]
        return [self._as_result(r, 0.6) for r in hit[:top_k]]

    @staticmethod
    def _dedupe_and_sort(rows: list[dict], preferred_type: str | None = None) -> list[dict]:
        deduped: dict[tuple[str, str], dict] = {}
        for row in rows:
            key = (row.get('title', ''), row.get('public_url', ''))
            current = deduped.get(key)
            if not current or row.get('score', 0) > current.get('score', 0):
                deduped[key] = row
        return sorted(
            deduped.values(),
            key=lambda row: (row.get('type') == preferred_type if preferred_type else False, row.get('score', 0)),
            reverse=True,
        )
