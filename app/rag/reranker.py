from app.rag.retriever import RetrievedChunk


class BaseReranker:
    def rerank(self, query: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        raise NotImplementedError


class NoOpReranker(BaseReranker):
    def rerank(self, query: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        return chunks
