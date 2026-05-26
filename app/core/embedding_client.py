import httpx

from app.core.config import settings


class EmbeddingClient:
    @staticmethod
    def _fallback(texts: list[str]) -> list[list[float]]:
        return [[0.0] * 8 for _ in texts]

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if settings.EMBEDDING_PROVIDER != 'openai_compatible' or not settings.EMBEDDING_API_KEY or not settings.EMBEDDING_BASE_URL:
            return self._fallback(texts)
        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
            resp = await client.post(
                f"{settings.EMBEDDING_BASE_URL.rstrip('/')}/embeddings",
                headers={'Authorization': f'Bearer {settings.EMBEDDING_API_KEY}'},
                json={'model': settings.EMBEDDING_MODEL, 'input': texts},
            )
            resp.raise_for_status()
            return [item['embedding'] for item in resp.json()['data']]

    def embed_texts_sync(self, texts: list[str]) -> list[list[float]]:
        if settings.EMBEDDING_PROVIDER != 'openai_compatible' or not settings.EMBEDDING_API_KEY or not settings.EMBEDDING_BASE_URL:
            return self._fallback(texts)
        with httpx.Client(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
            resp = client.post(
                f"{settings.EMBEDDING_BASE_URL.rstrip('/')}/embeddings",
                headers={'Authorization': f'Bearer {settings.EMBEDDING_API_KEY}'},
                json={'model': settings.EMBEDDING_MODEL, 'input': texts},
            )
            resp.raise_for_status()
            return [item['embedding'] for item in resp.json()['data']]
