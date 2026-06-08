from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.rag.retriever import RetrievedChunk


def _terms(text: str) -> set[str]:
    return {token for token in text.lower().replace('ё', 'е').split() if len(token) >= 3}


class BaseReranker:
    def rerank(self, query: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        raise NotImplementedError


class NoOpReranker(BaseReranker):
    def rerank(self, query: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        return chunks


class LexicalOverlapReranker(BaseReranker):
    def rerank(self, query: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        query_terms = _terms(query)
        if not query_terms:
            return chunks

        def score(chunk: RetrievedChunk) -> tuple[float, float]:
            text_terms = _terms(chunk.text)
            if not text_terms:
                return chunk.score, 0.0
            overlap = len(query_terms & text_terms) / max(len(query_terms), 1)
            return chunk.score + min(overlap * 0.08, 0.08), overlap

        return sorted(chunks, key=score, reverse=True)
