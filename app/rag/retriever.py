from pydantic import BaseModel
from app.core.config import settings
from app.core.chroma import get_chroma_client
from app.core.embedding_client import EmbeddingClient, EmbeddingNotConfiguredError
from app.rag.reranker import LexicalOverlapReranker, NoOpReranker


class RetrievedChunk(BaseModel):
    text: str
    metadata: dict
    score: float


class RagRetriever:
    def __init__(self) -> None:
        self.available = True
        self.collection = None
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
        try:
            qv = EmbeddingClient().embed_texts_sync([query])[0]
            res = self.collection.query(query_embeddings=[qv], n_results=top_k or settings.TOP_K)
        except EmbeddingNotConfiguredError:
            self.available = False
            return []
        except Exception:
            self.available = False
            return []
        out: list[RetrievedChunk] = []
        docs = res.get('documents', [[]])[0]
        metas = res.get('metadatas', [[]])[0]
        dists = res.get('distances', [[]])[0]
        for d, m, dist in zip(docs, metas, dists):
            score = 1.0 - float(dist or 1.0)
            if score >= settings.RAG_MIN_SCORE:
                out.append(RetrievedChunk(text=d, metadata=m or {}, score=score))
        reranker = LexicalOverlapReranker() if settings.ENABLE_RERANKER else NoOpReranker()
        return reranker.rerank(query, out)[:settings.RERANK_TOP_K if settings.ENABLE_RERANKER else len(out)]
