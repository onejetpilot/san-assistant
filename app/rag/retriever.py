from pydantic import BaseModel
import chromadb

from app.core.config import settings


class RetrievedChunk(BaseModel):
    text: str
    metadata: dict
    score: float


class RagRetriever:
    def __init__(self) -> None:
        self.available = True
        self.collection = None
        try:
            self.client = chromadb.PersistentClient(path=settings.CHROMA_PATH)
            self.collection = self.client.get_or_create_collection(settings.CHROMA_COLLECTION_PRODUCT_CHUNKS)
        except Exception:
            self.available = False

    def search(self, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
        if not self.collection:
            return []
        try:
            res = self.collection.query(query_texts=[query], n_results=top_k or settings.TOP_K)
        except Exception:
            self.available = False
            return []
        out: list[RetrievedChunk] = []
        docs = res.get('documents', [[]])[0]
        metas = res.get('metadatas', [[]])[0]
        dists = res.get('distances', [[]])[0]
        for d, m, dist in zip(docs, metas, dists):
            out.append(RetrievedChunk(text=d, metadata=m or {}, score=1.0 - float(dist or 1.0)))
        return out
