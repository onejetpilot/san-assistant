from __future__ import annotations

from pydantic import BaseModel

from app.core.chroma import get_chroma_client
from app.core.config import settings
from app.core.embedding_client import EmbeddingClient, EmbeddingNotConfiguredError
from app.indexes.sku_index import SkuIndex, SkuRecord
from app.rag.reranker import LexicalOverlapReranker, NoOpReranker
from app.utils.article_normalizer import normalize_sku
from app.utils.text import extract_article_candidate


MANDATORY_SECTIONS = [
    'VARIANTS (АРТИКУЛЫ)',
    'CONNECTIONS',
    'TECHNICAL SPECIFICATIONS',
    'INSTALLATION',
    'LIMITATIONS',
    'KEY FACTS',
    'FAQ',
]


class RetrievedChunk(BaseModel):
    text: str
    metadata: dict
    score: float


class RagRetriever:
    def __init__(self) -> None:
        self.available = True
        self.collection = None
        self.sku = SkuIndex.load(f"{settings.INDEXES_PATH}/sku_index.json")
        if not self.sku.data:
            self.sku = SkuIndex.load('./data/indexes/sku_index.json')
        if not EmbeddingClient.is_configured():
            self.available = False
            return
        try:
            self.client = get_chroma_client()
            self.collection = self.client.get_or_create_collection(settings.CHROMA_COLLECTION_PRODUCT_CHUNKS, embedding_function=None)
        except Exception:
            self.available = False

    def search(self, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
        if not self.collection:
            return []
        doc_id = self._resolve_doc_id(query)
        if doc_id:
            return self._search_within_document(query, doc_id, top_k=top_k)
        global_results = self._semantic_query(query, top_k=(top_k or settings.TOP_K) * 3)
        if not global_results:
            return []
        anchored_doc_id = self._pick_confident_doc_id(global_results)
        if anchored_doc_id:
            return self._search_within_document(query, anchored_doc_id, top_k=top_k)
        return self._finalize(query, global_results[:top_k or settings.TOP_K])

    def _resolve_doc_id(self, query: str) -> str | None:
        article = extract_article_candidate(query)
        normalized = normalize_sku(article)
        candidates = [normalized.normalized, normalized.base_article]
        for candidate in candidates:
            if not candidate:
                continue
            row = self.sku.lookup(candidate)
            if row and row.doc_id:
                return row.doc_id
        return None

    def _search_within_document(self, query: str, doc_id: str, top_k: int | None = None) -> list[RetrievedChunk]:
        mandatory = self._get_document_sections(doc_id, MANDATORY_SECTIONS)
        semantic = self._semantic_query(query, top_k=(top_k or settings.TOP_K) * 2, doc_id=doc_id)
        merged = self._merge_without_duplicates(mandatory + semantic)
        return self._finalize(query, merged[: max(top_k or settings.TOP_K, len(mandatory))])

    def _semantic_query(self, query: str, top_k: int, doc_id: str | None = None) -> list[RetrievedChunk]:
        try:
            qv = EmbeddingClient().embed_texts_sync([query])[0]
            where = {'doc_id': doc_id} if doc_id else None
            if where:
                try:
                    res = self.collection.query(query_embeddings=[qv], n_results=top_k, where=where)
                except TypeError:
                    res = self.collection.query(query_embeddings=[qv], n_results=top_k)
                results = self._to_chunks(res)
                if where:
                    results = [item for item in results if item.metadata.get('doc_id') == doc_id]
                return results
            res = self.collection.query(query_embeddings=[qv], n_results=top_k)
            return self._to_chunks(res)
        except EmbeddingNotConfiguredError:
            self.available = False
            return []
        except Exception:
            self.available = False
            return []

    def _get_document_sections(self, doc_id: str, sections: list[str]) -> list[RetrievedChunk]:
        try:
            try:
                res = self.collection.get(where={'doc_id': doc_id}, include=['documents', 'metadatas'])
            except TypeError:
                res = self.collection.get(include=['documents', 'metadatas'])
            docs = res.get('documents', []) or []
            metas = res.get('metadatas', []) or []
            chunks: list[RetrievedChunk] = []
            for doc_text, metadata in zip(docs, metas):
                metadata = metadata or {}
                if metadata.get('doc_id') != doc_id:
                    continue
                section = str(metadata.get('section', ''))
                if section in sections:
                    chunks.append(RetrievedChunk(text=doc_text, metadata=metadata, score=1.0))
            order = {section: idx for idx, section in enumerate(sections)}
            chunks.sort(key=lambda item: order.get(str(item.metadata.get('section', '')), 999))
            return self._merge_without_duplicates(chunks)
        except Exception:
            return []

    @staticmethod
    def _merge_without_duplicates(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        merged: list[RetrievedChunk] = []
        seen: set[tuple[str, str]] = set()
        for chunk in chunks:
            metadata = chunk.metadata or {}
            key = (str(metadata.get('doc_id', '')), str(metadata.get('section', '')) or chunk.text[:120])
            if key in seen:
                continue
            seen.add(key)
            merged.append(chunk)
        return merged

    @staticmethod
    def _pick_confident_doc_id(chunks: list[RetrievedChunk]) -> str | None:
        if not chunks:
            return None
        top = chunks[0]
        top_doc_id = str(top.metadata.get('doc_id', ''))
        if not top_doc_id:
            return None
        same_doc_hits = [chunk for chunk in chunks[:3] if str(chunk.metadata.get('doc_id', '')) == top_doc_id]
        if top.score >= 0.55 or len(same_doc_hits) >= 2:
            return top_doc_id
        return None

    @staticmethod
    def _to_chunks(res: dict) -> list[RetrievedChunk]:
        out: list[RetrievedChunk] = []
        docs = res.get('documents', [[]])[0]
        metas = res.get('metadatas', [[]])[0]
        dists = res.get('distances', [[]])[0]
        for d, m, dist in zip(docs, metas, dists):
            score = 1.0 - float(dist or 1.0)
            if score >= settings.RAG_MIN_SCORE:
                out.append(RetrievedChunk(text=d, metadata=m or {}, score=score))
        return out

    @staticmethod
    def _reranker():
        return LexicalOverlapReranker() if settings.ENABLE_RERANKER else NoOpReranker()

    def _finalize(self, query: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        reranked = self._reranker().rerank(query, chunks)
        return reranked[:settings.RERANK_TOP_K if settings.ENABLE_RERANKER else len(reranked)]
